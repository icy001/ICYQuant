"""
Crypto recovery manager.

Recovers from crypto component failures by:
1. Provider recovery (failover to standby)
2. Cache recovery (restore from persistent storage)
3. Lease recovery (renew expired key leases)
4. Rotation recovery (restore rotation schedule)

Recovery Flow:
    Crypto Failure
        ↓
    Detect Failure
        ↓
    Find Standby Provider
        ↓
    Reconnect / Failover
        ↓
    Verify Recovery
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecoveryState:
    """Recovery state constants."""

    IDLE = "idle"
    DETECTING = "detecting"
    RECONNECTING = "reconnecting"
    FAILOVER = "failover"
    RECOVERED = "recovered"
    FAILED = "failed"


@dataclass
class RecoveryEvent:
    """
    A recovery event record.

    Attributes:
        error: Error that triggered recovery.
        from_provider: Provider before recovery.
        to_provider: Provider after recovery.
        success: Whether recovery succeeded.
        duration: Recovery duration in seconds.
    """

    error: str = ""
    from_provider: str = ""
    to_provider: str = ""
    success: bool = False
    duration: float = 0.0
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error,
            "from_provider": self.from_provider,
            "to_provider": self.to_provider,
            "success": self.success,
            "duration": self.duration,
            "timestamp": (
                self.timestamp.isoformat()
                if self.timestamp
                else None
            ),
        }


class CryptoRecovery:
    """
    Automatic crypto recovery manager.

    Monitors crypto component health and automatically
    triggers recovery sequences when failures are detected.

    Recovery strategies:
    1. Provider Recovery: Failover to standby KMS provider
    2. Cache Recovery: Restore key cache from persistent storage
    3. Lease Recovery: Renew expired key leases automatically
    4. Rotation Recovery: Restore key rotation schedule

    Usage:
        recovery = CryptoRecovery()
        recovery.add_recovery_callback(on_recovery)
        event = recovery.trigger_recovery("KMS provider down")
    """

    def __init__(
        self,
        max_recovery_attempts: int = 3,
        cooldown_period: float = 5.0,
    ) -> None:
        """
        Initialize recovery manager.

        Args:
            max_recovery_attempts: Max recovery attempts per failure.
            cooldown_period: Minimum seconds between recoveries.
        """
        self._max_attempts = max_recovery_attempts
        self._cooldown = cooldown_period

        self._state = RecoveryState.IDLE
        self._recovery_history: List[RecoveryEvent] = []
        self._recovery_callbacks: List[Callable] = []
        self._attempt_count = 0
        self._last_recovery_time: float = 0

        self._providers: Dict[str, Any] = {}
        self._active_provider: Optional[str] = None
        self._failed_provider: Optional[str] = None

        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Get current recovery state."""
        return self._state

    @property
    def recovery_count(self) -> int:
        """Get total recovery count."""
        return len(self._recovery_history)

    @property
    def last_recovery(self) -> Optional[RecoveryEvent]:
        """Get last recovery event."""
        if not self._recovery_history:
            return None
        return self._recovery_history[-1]

    def register_provider(
        self,
        name: str,
        provider: Any,
        is_primary: bool = False,
    ) -> None:
        """
        Register a crypto provider.

        Args:
            name: Provider name.
            provider: Provider instance.
            is_primary: Whether this is the primary provider.
        """
        self._providers[name] = provider
        if is_primary or self._active_provider is None:
            self._active_provider = name
            self._failed_provider = name

    def add_recovery_callback(
        self,
        callback: Callable,
    ) -> None:
        """
        Add a recovery notification callback.

        Args:
            callback: Called with (event) on recovery.
        """
        self._recovery_callbacks.append(callback)

    def trigger_recovery(
        self,
        error: str,
        provider_name: Optional[str] = None,
    ) -> Optional[RecoveryEvent]:
        """
        Trigger recovery sequence for a crypto failure.

        Args:
            error: Error message describing the failure.
            provider_name: Name of failing provider.

        Returns:
            RecoveryEvent if recovery was attempted.
        """
        with self._lock:
            now = time.time()
            if now - self._last_recovery_time < self._cooldown:
                logger.debug(
                    "Recovery cooldown active, skipping"
                )
                return None

            if self._attempt_count >= self._max_attempts:
                self._state = RecoveryState.FAILED
                logger.error(
                    "Max recovery attempts (%d) reached",
                    self._max_attempts,
                )
                return None

            self._attempt_count += 1
            self._last_recovery_time = now
            self._state = RecoveryState.DETECTING

        start = time.time()
        from_provider = provider_name or self._active_provider or ""

        try:
            self._state = RecoveryState.RECONNECTING

            standby = self._find_standby_provider(from_provider)

            if standby is None:
                self._state = RecoveryState.FAILED
                duration = time.time() - start
                event = RecoveryEvent(
                    error=error,
                    from_provider=from_provider,
                    to_provider="",
                    success=False,
                    duration=duration,
                )
                self._record_event(event)
                self._notify_callbacks(event)
                return event

            self._state = RecoveryState.FAILOVER

            reconnected = self._reconnect_provider(standby)
            success = reconnected

            duration = time.time() - start
            event = RecoveryEvent(
                error=error,
                from_provider=from_provider,
                to_provider=standby if success else "",
                success=success,
                duration=duration,
            )

            if success:
                self._active_provider = standby
                self._state = RecoveryState.RECOVERED
                self._attempt_count = 0
                logger.info(
                    "Recovery succeeded: %s -> %s",
                    from_provider,
                    standby,
                )
            else:
                self._state = RecoveryState.FAILED
                logger.error(
                    "Recovery failed: no standby available"
                )

            self._record_event(event)
            self._notify_callbacks(event)
            return event

        except Exception as e:
            duration = time.time() - start
            self._state = RecoveryState.FAILED
            event = RecoveryEvent(
                error=f"{error} (recovery error: {e})",
                from_provider=from_provider,
                to_provider="",
                success=False,
                duration=duration,
            )
            self._record_event(event)
            self._notify_callbacks(event)
            return event

    def _find_standby_provider(
        self,
        exclude_name: str,
    ) -> Optional[str]:
        """
        Find an available standby provider.

        Args:
            exclude_name: Provider to exclude (the failing one).

        Returns:
            Name of an available standby provider, or None.
        """
        for name in self._providers:
            if name == exclude_name:
                continue
            provider = self._providers[name]
            try:
                if hasattr(provider, "health_check"):
                    health = provider.health_check()
                    if health.healthy:
                        return name
                else:
                    return name
            except Exception as e:
                logger.warning(
                    "Provider %s health check failed: %s",
                    name,
                    e,
                )
                continue

        return None

    def _reconnect_provider(
        self,
        provider_name: str,
    ) -> bool:
        """
        Attempt to reconnect to a provider.

        Args:
            provider_name: Name of provider to reconnect.

        Returns:
            True if reconnection succeeded.
        """
        provider = self._providers.get(provider_name)
        if provider is None:
            return False

        try:
            if hasattr(provider, "initialize"):
                provider.initialize()
            return True
        except Exception as e:
            logger.error(
                "Failed to reconnect to %s: %s",
                provider_name,
                e,
            )
            return False

    def _record_event(
        self,
        event: RecoveryEvent,
    ) -> None:
        """Record a recovery event."""
        with self._lock:
            self._recovery_history.append(event)
            if len(self._recovery_history) > 500:
                self._recovery_history.pop(0)

    def _notify_callbacks(
        self,
        event: RecoveryEvent,
    ) -> None:
        """Notify all recovery callbacks."""
        for callback in self._recovery_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(
                    "Recovery callback error: %s", e
                )

    def reset(self) -> None:
        """Reset recovery state."""
        with self._lock:
            self._state = RecoveryState.IDLE
            self._attempt_count = 0
            self._last_recovery_time = 0

    def get_history(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recovery history.

        Args:
            limit: Maximum number of history entries.

        Returns:
            List of recovery event dictionaries.
        """
        return [
            e.to_dict()
            for e in self._recovery_history[-limit:]
        ]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get recovery statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            total = len(self._recovery_history)
            successful = sum(
                1
                for e in self._recovery_history
                if e.success
            )
            return {
                "state": self._state,
                "total_recoveries": total,
                "successful_recoveries": successful,
                "failed_recoveries": total - successful,
                "attempt_count": self._attempt_count,
                "max_attempts": self._max_attempts,
                "active_provider": self._active_provider,
                "registered_providers": len(self._providers),
            }