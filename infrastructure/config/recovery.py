"""
Automatic recovery manager.

Recovers from configuration failures by:
1. Detecting configuration errors
2. Rolling back to last stable snapshot
3. Recovering the last known good configuration
4. Notifying operators

Recovery Flow:
    Configuration Error
        ↓
    Rollback Snapshot
        ↓
    Recover Last Stable Version
        ↓
    Notify Operator
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .dynamic.snapshot import DynamicSnapshot, DynamicSnapshotStore

logger = logging.getLogger(__name__)


class RecoveryState:
    """Recovery state constants."""
    IDLE = "idle"
    DETECTING = "detecting"
    ROLLING_BACK = "rolling_back"
    RECOVERING = "recovering"
    NOTIFIED = "notified"
    FAILED = "failed"
    RECOVERED = "recovered"


class RecoveryEvent:
    """
    A recovery event record.

    Attributes:
        error: Error that triggered recovery.
        from_version: Version before error.
        to_version: Version recovered to.
        timestamp: When recovery occurred.
        success: Whether recovery succeeded.
    """

    def __init__(
        self,
        error: str,
        from_version: int,
        to_version: int,
        success: bool,
        duration: float = 0.0,
    ) -> None:
        self.error = error
        self.from_version = from_version
        self.to_version = to_version
        self.success = success
        self.duration = duration
        self.timestamp = datetime.utcnow()

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "error": self.error,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "success": self.success,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
        }


class AutomaticRecovery:
    """
    Automatic configuration recovery manager.

    Monitors configuration health and automatically
    triggers rollback when failures are detected.

    Usage:
        recovery = AutomaticRecovery(snapshot_store)
        recovery.add_failure_callback(notify_ops)

        # Register failure
        recovery.on_failure("Validation failed", current_version=5)
    """

    def __init__(
        self,
        snapshot_store: Optional[DynamicSnapshotStore] = None,
        max_recovery_attempts: int = 3,
        cooldown_period: float = 5.0,
    ) -> None:
        """
        Initialize recovery manager.

        Args:
            snapshot_store: Snapshot store for rollback.
            max_recovery_attempts: Max recovery attempts.
            cooldown_period: Minimum seconds between recoveries.
        """
        self._snapshot_store = snapshot_store or DynamicSnapshotStore()
        self._max_attempts = max_recovery_attempts
        self._cooldown = cooldown_period
        self._state = RecoveryState.IDLE
        self._recovery_history: List[RecoveryEvent] = []
        self._failure_callbacks: List[Callable] = []
        self._attempt_count = 0
        self._last_recovery_time: float = 0
        self._lock = threading.Lock()

    @property
    def state(
        self,
    ) -> str:
        """Get current state."""
        return self._state

    @property
    def recovery_count(
        self,
    ) -> int:
        """Get total recovery count."""
        return len(self._recovery_history)

    @property
    def last_recovery(
        self,
    ) -> Optional[RecoveryEvent]:
        """Get last recovery event."""
        if not self._recovery_history:
            return None
        return self._recovery_history[-1]

    def add_failure_callback(
        self,
        callback: Callable,
    ) -> None:
        """
        Add a failure notification callback.

        Args:
            callback: Called with (error, recovery_event) on failure.
        """
        self._failure_callbacks.append(callback)

    def on_failure(
        self,
        error: str,
        current_version: Optional[int] = None,
    ) -> Optional[RecoveryEvent]:
        """
        Handle a configuration failure.

        Triggers automatic recovery if conditions are met.

        Args:
            error: Error message.
            current_version: Current configuration version.

        Returns:
            RecoveryEvent if recovery was attempted.
        """
        with self._lock:
            # Check cooldown
            now = time.time()
            if now - self._last_recovery_time < self._cooldown:
                return None

            # Check attempt limit
            if self._attempt_count >= self._max_attempts:
                self._state = RecoveryState.FAILED
                return None

            self._attempt_count += 1
            self._last_recovery_time = now
            self._state = RecoveryState.ROLLING_BACK

        start = time.time()

        try:
            # Find last stable version
            target_version = self._find_stable_version(current_version)
            if target_version is None:
                event = RecoveryEvent(
                    error=error,
                    from_version=current_version or 0,
                    to_version=0,
                    success=False,
                    duration=time.time() - start,
                )
                self._recovery_history.append(event)
                self._notify_callbacks(error, event)
                self._state = RecoveryState.FAILED
                return event

            # Perform rollback
            restored = self._snapshot_store.rollback_to(target_version)
            success = restored is not None

            duration = time.time() - start
            event = RecoveryEvent(
                error=error,
                from_version=current_version or 0,
                to_version=target_version,
                success=success,
                duration=duration,
            )

            self._recovery_history.append(event)
            self._notify_callbacks(error, event)

            if success:
                self._state = RecoveryState.RECOVERED
                self._attempt_count = 0  # Reset on success
            else:
                self._state = RecoveryState.FAILED

            return event

        except Exception as e:
            duration = time.time() - start
            event = RecoveryEvent(
                error=f"{error} (recovery failed: {e})",
                from_version=current_version or 0,
                to_version=0,
                success=False,
                duration=duration,
            )
            self._recovery_history.append(event)
            self._notify_callbacks(error, event)
            self._state = RecoveryState.FAILED
            return event

    def _find_stable_version(
        self,
        current_version: Optional[int],
    ) -> Optional[int]:
        """
        Find the last stable configuration version.

        Args:
            current_version: Current version to recover from.

        Returns:
            Target version for rollback.
        """
        history = self._snapshot_store.get_history()
        if not history:
            return None

        # Try to find a version before the current one
        if current_version:
            for snap in reversed(history):
                if snap.version < current_version:
                    # Verify integrity
                    if snap.verify_integrity():
                        return snap.version

        # Fallback to the oldest in history
        if history:
            return history[0].version

        return None

    def _notify_callbacks(
        self,
        error: str,
        event: RecoveryEvent,
    ) -> None:
        """Notify all failure callbacks."""
        for callback in self._failure_callbacks:
            try:
                callback(error, event)
            except Exception:
                pass

    def reset(
        self,
    ) -> None:
        """Reset recovery state."""
        with self._lock:
            self._state = RecoveryState.IDLE
            self._attempt_count = 0
            self._last_recovery_time = 0

    def get_history(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recovery history."""
        return [e.to_dict() for e in self._recovery_history[-limit:]]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get recovery statistics."""
        return {
            "state": self._state,
            "total_recoveries": len(self._recovery_history),
            "successful_recoveries": sum(
                1 for e in self._recovery_history if e.success
            ),
            "failed_recoveries": sum(
                1 for e in self._recovery_history if not e.success
            ),
            "attempt_count": self._attempt_count,
            "max_attempts": self._max_attempts,
        }
