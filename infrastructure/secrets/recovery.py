"""
Secrets recovery mechanisms.

Provides recovery capabilities for secrets
platform components, including provider recovery,
cache recovery, lease recovery, and rotation
recovery, with event tracking and callbacks.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecoveryType(str, Enum):
    """Types of recovery operations."""

    PROVIDER = "provider"
    CACHE = "cache"
    LEASE = "lease"
    ROTATION = "rotation"


class RecoveryStatus(str, Enum):
    """Recovery operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RecoveryEvent:
    """
    A recovery event record.

    Attributes:
        recovery_type: Type of recovery operation.
        status: Current recovery status.
        target: Target of recovery (e.g., provider name).
        timestamp: When the event occurred.
        duration_ms: Recovery duration in milliseconds.
        details: Additional event details.
        error: Error message if failed.
    """

    recovery_type: str = ""
    status: str = ""
    target: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recovery_type": self.recovery_type,
            "status": self.status,
            "target": self.target,
            "timestamp": self.timestamp.isoformat() + "Z",
            "duration_ms": self.duration_ms,
            "details": self.details,
            "error": self.error,
        }


@dataclass
class RecoveryRequest:
    """
    A recovery request.

    Attributes:
        recovery_type: Type of recovery needed.
        target: Target to recover.
        reason: Reason for recovery.
        parameters: Additional recovery parameters.
    """

    recovery_type: RecoveryType = RecoveryType.PROVIDER
    target: str = ""
    reason: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)


class SecretsRecovery:
    """
    Secrets recovery manager.

    Manages recovery operations for provider,
    cache, lease, and rotation failures, with
    configurable callbacks and event tracking.

    Usage:
        recovery = SecretsRecovery(provider=provider, cache=cache)
        recovery.set_recovery_handler(RecoveryType.PROVIDER, my_handler)
        result = recovery.trigger_recovery(RecoveryRequest(
            recovery_type=RecoveryType.PROVIDER,
            target="primary_vault",
            reason="connection_lost",
        ))
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        cache: Optional[Any] = None,
        lease: Optional[Any] = None,
        rotation: Optional[Any] = None,
        max_history: int = 500,
    ) -> None:
        """
        Initialize recovery manager.

        Args:
            provider: SecretsProvider instance.
            cache: SecretsCache instance.
            lease: Lease manager instance.
            rotation: Rotation manager instance.
            max_history: Maximum history entries.
        """
        self._provider = provider
        self._cache = cache
        self._lease = lease
        self._rotation = rotation
        self._max_history = max_history

        self._lock = threading.RLock()

        # Recovery handlers by type
        self._handlers: Dict[RecoveryType, Callable[[RecoveryRequest], bool]] = {}

        # Recovery callbacks
        self._on_recovery_start: Optional[Callable[[RecoveryRequest], None]] = None
        self._on_recovery_complete: Optional[Callable[[RecoveryEvent], None]] = None
        self._on_recovery_failure: Optional[
            Callable[[RecoveryRequest, str], None]
        ] = None

        # Event history
        self._events: List[RecoveryEvent] = []

        # Active recoveries
        self._active_recoveries: Dict[str, RecoveryEvent] = {}

        # Statistics
        self._total_recoveries = 0
        self._successful_recoveries = 0
        self._failed_recoveries = 0
        self._by_type: Dict[str, int] = {}

    # ── Configuration ──

    def set_recovery_handler(
        self,
        recovery_type: RecoveryType,
        handler: Callable[[RecoveryRequest], bool],
    ) -> None:
        """
        Set a recovery handler for a specific type.

        Args:
            recovery_type: Type of recovery.
            handler: Callable(RecoveryRequest) -> bool.
        """
        with self._lock:
            self._handlers[recovery_type] = handler

    def set_on_recovery_start(
        self,
        callback: Callable[[RecoveryRequest], None],
    ) -> None:
        """
        Set callback for recovery start.

        Args:
            callback: Called when recovery begins.
        """
        self._on_recovery_start = callback

    def set_on_recovery_complete(
        self,
        callback: Callable[[RecoveryEvent], None],
    ) -> None:
        """
        Set callback for recovery completion.

        Args:
            callback: Called when recovery completes.
        """
        self._on_recovery_complete = callback

    def set_on_recovery_failure(
        self,
        callback: Callable[[RecoveryRequest, str], None],
    ) -> None:
        """
        Set callback for recovery failure.

        Args:
            callback: Called when recovery fails.
        """
        self._on_recovery_failure = callback

    # ── Trigger Recovery ──

    def trigger_recovery(
        self,
        request: RecoveryRequest,
    ) -> RecoveryEvent:
        """
        Trigger a recovery operation.

        Args:
            request: Recovery request details.

        Returns:
            RecoveryEvent with the result.
        """
        with self._lock:
            event = RecoveryEvent(
                recovery_type=request.recovery_type.value,
                status=RecoveryStatus.IN_PROGRESS.value,
                target=request.target,
                details={
                    "reason": request.reason,
                    "parameters": request.parameters,
                },
            )

            recovery_id = f"{request.recovery_type.value}:{request.target}"
            self._active_recoveries[recovery_id] = event

            self._total_recoveries += 1
            type_key = request.recovery_type.value
            self._by_type[type_key] = self._by_type.get(type_key, 0) + 1

            if self._on_recovery_start:
                try:
                    self._on_recovery_start(request)
                except Exception as e:
                    logger.error("Recovery start callback error: %s", e)

        start_time = time.time()
        success = False
        error_msg = ""

        try:
            success = self._execute_recovery(request)
        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Recovery failed for %s/%s: %s",
                request.recovery_type.value,
                request.target,
                e,
            )

        elapsed_ms = (time.time() - start_time) * 1000

        with self._lock:
            event.duration_ms = elapsed_ms
            event.status = (
                RecoveryStatus.COMPLETED.value
                if success
                else RecoveryStatus.FAILED.value
            )
            event.error = error_msg

            recovery_id = f"{request.recovery_type.value}:{request.target}"
            self._active_recoveries.pop(recovery_id, None)

            if success:
                self._successful_recoveries += 1
            else:
                self._failed_recoveries += 1
                if self._on_recovery_failure:
                    try:
                        self._on_recovery_failure(request, error_msg)
                    except Exception as e:
                        logger.error("Recovery failure callback error: %s", e)

            self._events.append(event)
            if len(self._events) > self._max_history:
                self._events = self._events[-self._max_history:]

            if self._on_recovery_complete:
                try:
                    self._on_recovery_complete(event)
                except Exception as e:
                    logger.error("Recovery complete callback error: %s", e)

        return event

    def _execute_recovery(self, request: RecoveryRequest) -> bool:
        """
        Execute recovery based on type.

        Args:
            request: Recovery request.

        Returns:
            True if recovery succeeded.
        """
        recovery_type = request.recovery_type

        if recovery_type in self._handlers:
            handler = self._handlers[recovery_type]
            return handler(request)

        if recovery_type == RecoveryType.PROVIDER:
            return self._recover_provider(request)
        elif recovery_type == RecoveryType.CACHE:
            return self._recover_cache(request)
        elif recovery_type == RecoveryType.LEASE:
            return self._recover_lease(request)
        elif recovery_type == RecoveryType.ROTATION:
            return self._recover_rotation(request)
        else:
            logger.warning("Unknown recovery type: %s", recovery_type)
            return False

    # ── Default Recovery Handlers ──

    def _recover_provider(self, request: RecoveryRequest) -> bool:
        """
        Recover a secrets provider.

        Attempts to restore provider connectivity
        and verify health.

        Args:
            request: Recovery request.

        Returns:
            True if recovery succeeded.
        """
        if self._provider is None:
            logger.warning("No provider to recover")
            return False

        try:
            if hasattr(self._provider, "health_check"):
                health = self._provider.health_check()
                if isinstance(health, dict) and health.get("healthy", False):
                    logger.info(
                        "Provider recovery successful: %s", request.target
                    )
                    return True

            if hasattr(self._provider, "reconnect"):
                self._provider.reconnect()
                logger.info(
                    "Provider reconnected: %s", request.target
                )
                return True

            if hasattr(self._provider, "reset"):
                self._provider.reset()
                logger.info(
                    "Provider reset: %s", request.target
                )
                return True

            logger.info(
                "Provider recovery attempted: %s", request.target
            )
            return True
        except Exception as e:
            logger.error(
                "Provider recovery failed: %s - %s", request.target, e
            )
            return False

    def _recover_cache(self, request: RecoveryRequest) -> bool:
        """
        Recover secrets cache.

        Clears corrupted cache entries and
        restores cache consistency.

        Args:
            request: Recovery request.

        Returns:
            True if recovery succeeded.
        """
        if self._cache is None:
            logger.warning("No cache to recover")
            return False

        try:
            if hasattr(self._cache, "clear"):
                self._cache.clear()
                logger.info("Cache cleared for recovery: %s", request.target)

            if hasattr(self._cache, "cleanup_expired"):
                removed = self._cache.cleanup_expired()
                logger.info(
                    "Cache recovered: %d expired entries removed", removed
                )

            return True
        except Exception as e:
            logger.error(
                "Cache recovery failed: %s - %s", request.target, e
            )
            return False

    def _recover_lease(self, request: RecoveryRequest) -> bool:
        """
        Recover a lease.

        Attempts to renew or restore a lease
        that has expired or been invalidated.

        Args:
            request: Recovery request.

        Returns:
            True if recovery succeeded.
        """
        if self._lease is None:
            logger.warning("No lease manager to recover")
            return False

        try:
            if hasattr(self._lease, "renew"):
                lease_id = request.parameters.get("lease_id", request.target)
                self._lease.renew(lease_id)
                logger.info(
                    "Lease renewed: %s", lease_id
                )
                return True

            if hasattr(self._lease, "restore"):
                self._lease.restore(request.target)
                logger.info(
                    "Lease restored: %s", request.target
                )
                return True

            logger.info(
                "Lease recovery attempted: %s", request.target
            )
            return True
        except Exception as e:
            logger.error(
                "Lease recovery failed: %s - %s", request.target, e
            )
            return False

    def _recover_rotation(self, request: RecoveryRequest) -> bool:
        """
        Recover a failed rotation.

        Attempts to rollback or retry a
        rotation that failed mid-operation.

        Args:
            request: Recovery request.

        Returns:
            True if recovery succeeded.
        """
        if self._rotation is None:
            logger.warning("No rotation manager to recover")
            return False

        try:
            if hasattr(self._rotation, "rollback"):
                key = request.parameters.get("key", request.target)
                self._rotation.rollback(key)
                logger.info(
                    "Rotation rolled back: %s", key
                )
                return True

            if hasattr(self._rotation, "retry"):
                key = request.parameters.get("key", request.target)
                self._rotation.retry(key)
                logger.info(
                    "Rotation retried: %s", key
                )
                return True

            logger.info(
                "Rotation recovery attempted: %s", request.target
            )
            return True
        except Exception as e:
            logger.error(
                "Rotation recovery failed: %s - %s", request.target, e
            )
            return False

    # ── Active Recoveries ──

    def get_active_recoveries(self) -> List[Dict[str, Any]]:
        """
        Get currently active recovery operations.

        Returns:
            List of active recovery event dicts.
        """
        with self._lock:
            return [e.to_dict() for e in self._active_recoveries.values()]

    def cancel_recovery(self, recovery_id: str) -> bool:
        """
        Cancel an active recovery.

        Args:
            recovery_id: Recovery ID to cancel.

        Returns:
            True if recovery was cancelled.
        """
        with self._lock:
            event = self._active_recoveries.pop(recovery_id, None)
            if event:
                event.status = RecoveryStatus.CANCELLED.value
                self._events.append(event)
                if len(self._events) > self._max_history:
                    self._events = self._events[-self._max_history:]
                logger.info("Recovery cancelled: %s", recovery_id)
                return True
            return False

    # ── History & Stats ──

    def get_history(
        self,
        limit: int = 100,
        recovery_type: Optional[RecoveryType] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recovery event history.

        Args:
            limit: Maximum number of events.
            recovery_type: Optional type filter.

        Returns:
            List of recovery event dicts.
        """
        with self._lock:
            events = list(reversed(self._events))
            if recovery_type:
                events = [
                    e for e in events if e.recovery_type == recovery_type.value
                ]
            return [e.to_dict() for e in events[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get recovery statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            success_rate = (
                self._successful_recoveries / self._total_recoveries
                if self._total_recoveries > 0
                else 0.0
            )
            return {
                "total_recoveries": self._total_recoveries,
                "successful": self._successful_recoveries,
                "failed": self._failed_recoveries,
                "success_rate": round(success_rate, 4),
                "by_type": dict(self._by_type),
                "active_recoveries": len(self._active_recoveries),
                "history_size": len(self._events),
                "components": {
                    "provider": self._provider is not None,
                    "cache": self._cache is not None,
                    "lease": self._lease is not None,
                    "rotation": self._rotation is not None,
                },
            }