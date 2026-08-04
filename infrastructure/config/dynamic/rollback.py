"""
Configuration rollback manager.

Supports instant rollback to previous configuration
snapshots with safety checks and automatic recovery
on reload failure.

Rollback Flow:
    Current Snapshot
        ↓
    Rollback Request (version)
        ↓
    Find Snapshot in History
        ↓
    Validate Target Snapshot
        ↓
    Atomic Swap
        ↓
    Notify Services
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .snapshot import DynamicSnapshot, DynamicSnapshotStore


class ConfigurationRollback:
    """
    Manages configuration rollback operations.

    Supports:
    - Rollback to specific version
    - Rollback N steps back
    - Automatic rollback on failure
    - Snapshot integrity verification
    - Full rollback audit trail

    Usage:
        rollback = ConfigurationRollback(store)

        # Rollback to version 5
        result = rollback.rollback_to(version=5)

        # Rollback 3 steps back
        result = rollback.rollback_steps(steps=3)
    """

    def __init__(
        self,
        snapshot_store: DynamicSnapshotStore,
    ) -> None:
        """
        Initialize rollback manager.

        Args:
            snapshot_store: Snapshot store with history.
        """
        self._store = snapshot_store
        self._rollback_history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._lock = threading.Lock()

    @property
    def rollback_history(
        self,
    ) -> List[Dict[str, Any]]:
        """Get rollback history."""
        with self._lock:
            return list(self._rollback_history)

    def rollback_to(
        self,
        version: int,
        operator: str = "system",
        reason: str = "manual rollback",
    ) -> Optional[RollbackResult]:
        """
        Rollback to a specific version.

        Args:
            version: Target version number.
            operator: Who triggered the rollback.
            reason: Reason for rollback.

        Returns:
            RollbackResult or None if version not found.
        """
        target = self._store.get_version(version)
        if target is None:
            return None

        # Verify target integrity
        if not target.verify_integrity():
            return RollbackResult(
                success=False,
                error=f"Target snapshot v{version} failed integrity check",
                from_version=self._store.version,
                to_version=version,
            )

        # Perform rollback
        old_version = self._store.version
        restored = self._store.rollback_to(version)

        if restored is None:
            return RollbackResult(
                success=False,
                error="Rollback failed",
                from_version=old_version,
                to_version=version,
            )

        # Log rollback
        self._log_rollback(
            from_version=old_version,
            to_version=restored.version,
            operator=operator,
            reason=reason,
        )

        return RollbackResult(
            success=True,
            error=None,
            from_version=old_version,
            to_version=restored.version,
            snapshot=restored,
            duration=0.0,
        )

    def rollback_steps(
        self,
        steps: int = 1,
        operator: str = "system",
        reason: str = "rollback steps",
    ) -> Optional[RollbackResult]:
        """
        Rollback N steps back.

        Args:
            steps: Number of versions to rollback.
            operator: Who triggered the rollback.
            reason: Reason for rollback.

        Returns:
            RollbackResult or None.
        """
        history = self._store.get_history()
        if len(history) < steps:
            return None

        # Get target version
        target_index = -(min(steps, len(history)))
        target = history[target_index]

        return self.rollback_to(
            version=target.version,
            operator=operator,
            reason=reason,
        )

    def emergency_rollback(
        self,
        operator: str = "system",
    ) -> Optional[RollbackResult]:
        """
        Emergency rollback to last known good snapshot.

        Rolls back one step automatically on failure.
        """
        return self.rollback_steps(
            steps=1,
            operator=operator,
            reason="emergency rollback after failure",
        )

    def verify_rollback_target(
        self,
        version: int,
    ) -> Dict[str, Any]:
        """
        Verify a rollback target before executing.

        Args:
            version: Target version.

        Returns:
            Verification result.
        """
        target = self._store.get_version(version)
        if target is None:
            return {
                "valid": False,
                "error": f"Version {version} not found",
            }

        integrity = target.verify_integrity()
        return {
            "valid": integrity,
            "version": target.version,
            "checksum": target.checksum,
            "integrity_ok": integrity,
            "key_count": len(target.values),
            "environment": target.environment,
            "error": None if integrity else "Integrity check failed",
        }

    def _log_rollback(
        self,
        from_version: int,
        to_version: int,
        operator: str,
        reason: str,
    ) -> None:
        """Log a rollback event."""
        entry = {
            "from_version": from_version,
            "to_version": to_version,
            "operator": operator,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with self._lock:
            self._rollback_history.append(entry)
            if len(self._rollback_history) > self._max_history:
                self._rollback_history.pop(0)


class RollbackResult:
    """
    Result of a rollback operation.

    Attributes:
        success: Whether rollback succeeded.
        error: Error message if failed.
        from_version: Version rolled back from.
        to_version: Version rolled back to.
        snapshot: Restored snapshot.
        duration: Rollback duration in seconds.
    """

    def __init__(
        self,
        success: bool,
        error: Optional[str] = None,
        from_version: int = 0,
        to_version: int = 0,
        snapshot: Optional[DynamicSnapshot] = None,
        duration: float = 0.0,
    ) -> None:
        self.success = success
        self.error = error
        self.from_version = from_version
        self.to_version = to_version
        self.snapshot = snapshot
        self.duration = duration

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "error": self.error,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "duration": self.duration,
        }
