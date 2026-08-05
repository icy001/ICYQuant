"""Service recovery for ICYQuant service discovery.

Provides ``ServiceRecovery`` for orchestrating recovery of failed
service instances. Recovery flow:
    Service Restart -> Heartbeat Resume -> Lease Recreate -> Registry Update

Supports automatic recovery, state sync, and snapshot restore.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .events import ServiceEvent, ServiceEventBus, ServiceEventType
from .exceptions import ServiceDiscoveryError
from .lease import LeaseManager

logger = logging.getLogger(__name__)


class ServiceRecovery:
    """Orchestrates recovery of failed service instances.

    Args:
        lease_manager: Optional ``LeaseManager`` for lease recreation.
        registry: Optional registry for state updates.
        event_bus: Optional ``ServiceEventBus`` for recovery events.
        max_attempts: Maximum recovery attempts per instance.
        backoff_base: Base seconds for exponential backoff.
    """

    def __init__(
        self,
        lease_manager: Optional[LeaseManager] = None,
        registry: Any = None,
        event_bus: Optional[ServiceEventBus] = None,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        self._lease_manager = lease_manager
        self._registry = registry
        self._event_bus = event_bus
        self._max_attempts = max(int(max_attempts), 1)
        self._backoff_base = float(backoff_base) if backoff_base > 0 else 2.0
        self._lock = threading.RLock()
        self._recovering: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._attempt_count = 0
        self._success_count = 0
        self._failure_count = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    # ── Public API ──

    async def recover(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Recover a service instance.

        Performs the full recovery flow, retrying up to
        ``max_attempts`` times with exponential backoff.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the recovery outcome.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            existing = self._recovering.get(key)
            if existing and existing.get("status") == "in_progress":
                return {
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "recovered": False,
                    "message": "Recovery already in progress.",
                }
            self._recovering[key] = {
                "service_name": service_name,
                "instance_id": instance_id,
                "status": "in_progress",
                "started_at": time.time(),
                "attempts": 0,
            }

        try:
            result = await self._recover_with_retries(
                service_name, instance_id
            )
        except Exception as exc:
            logger.exception(
                "Recovery failed for '%s/%s': %s",
                service_name,
                instance_id,
                exc,
            )
            result = {
                "service_name": service_name,
                "instance_id": instance_id,
                "recovered": False,
                "error": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
            }

        with self._lock:
            record = self._recovering.pop(key, None)
            self._record_history(result)
        return result

    async def attempt_recovery(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Perform a single recovery attempt.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the attempt outcome.
        """
        start = time.monotonic()
        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "recovered": False,
            "stages": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._attempt_count += 1

        # Stage 1: Service Restart (best-effort hook).
        result["stages"]["restart"] = await self._restart_service(
            service_name, instance_id
        )

        # Stage 2: Heartbeat Resume (best-effort hook).
        result["stages"]["heartbeat_resume"] = await self._resume_heartbeat(
            service_name, instance_id
        )

        # Stage 3: Lease Recreate.
        result["stages"]["lease_recreate"] = await self._recreate_lease(
            service_name, instance_id
        )

        # Stage 4: Registry Update.
        result["stages"]["registry_update"] = await self._update_registry(
            service_name, instance_id
        )

        recovered = all(
            stage.get("success", False) is not False
            for stage in result["stages"].values()
            if isinstance(stage, dict)
        ) and result["stages"].get("lease_recreate", {}).get("success", False)
        result["recovered"] = recovered
        result["latency_ms"] = (time.monotonic() - start) * 1000.0

        with self._lock:
            if recovered:
                self._success_count += 1
            else:
                self._failure_count += 1

        await self._publish_recovery_event(service_name, instance_id, recovered)
        return result

    def is_recovering(self, service_name: str, instance_id: str) -> bool:
        """Return whether a recovery is currently in progress."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._recovering.get(key)
            return bool(record and record.get("status") == "in_progress")

    def get_recovery_history(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Return recovery history, optionally filtered by service."""
        with self._lock:
            history = list(self._history)
        if service_name is None:
            return history
        return [h for h in history if h.get("service_name") == service_name]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the recovery manager."""
        with self._lock:
            return {
                "in_progress_count": len(self._recovering),
                "attempt_count": self._attempt_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "history_size": len(self._history),
                "max_attempts": self._max_attempts,
                "lease_manager_attached": self._lease_manager is not None,
                "registry_attached": self._registry is not None,
                "event_bus_attached": self._event_bus is not None,
            }

    # ── Recovery stages ──

    async def _restart_service(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Best-effort service restart hook."""
        if self._registry is None:
            return {"success": True, "message": "No registry; skipped restart."}
        method = getattr(self._registry, "restart", None)
        if not callable(method):
            return {
                "success": True,
                "message": "No restart hook on registry; skipped.",
            }
        try:
            result = method(service_name, instance_id)
            if asyncio.iscoroutine(result):
                await result
            return {"success": True, "message": "Service restarted."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _resume_heartbeat(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Best-effort heartbeat resume hook."""
        return {
            "success": True,
            "message": "Heartbeat resume is a no-op placeholder.",
        }

    async def _recreate_lease(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Recreate the lease for the instance, if a manager is attached."""
        if self._lease_manager is None:
            return {
                "success": True,
                "message": "No lease manager; skipped lease recreate.",
            }
        try:
            create_method = getattr(self._lease_manager, "create_lease", None)
            if create_method is None:
                return {"success": False, "error": "create_lease unavailable."}
            result = create_method(service_name, instance_id)
            if asyncio.iscoroutine(result):
                await result
            return {"success": True, "message": "Lease recreated."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _update_registry(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Update the registry to mark the instance as healthy."""
        if self._registry is None:
            return {
                "success": True,
                "message": "No registry; skipped registry update.",
            }
        for method_name in ("mark_healthy", "update_status", "register"):
            method = getattr(self._registry, method_name, None)
            if callable(method):
                try:
                    result = method(service_name, instance_id)
                    if asyncio.iscoroutine(result):
                        await result
                    return {
                        "success": True,
                        "message": f"Registry updated via {method_name}.",
                    }
                except Exception as exc:
                    return {"success": False, "error": str(exc)}
        return {"success": True, "message": "No registry update method."}

    # ── Internal helpers ──

    async def _recover_with_retries(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Retry recovery with exponential backoff."""
        last_result: Dict[str, Any] = {}
        for attempt in range(1, self._max_attempts + 1):
            with self._lock:
                record = self._recovering.get(
                    self._make_key(service_name, instance_id)
                )
                if record is not None:
                    record["attempts"] = attempt
            logger.info(
                "Recovery attempt %d/%d for '%s/%s'.",
                attempt,
                self._max_attempts,
                service_name,
                instance_id,
            )
            try:
                last_result = await self.attempt_recovery(
                    service_name, instance_id
                )
            except Exception as exc:
                last_result = {
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "recovered": False,
                    "error": str(exc),
                }
            if last_result.get("recovered"):
                last_result["attempts"] = attempt
                return last_result
            if attempt < self._max_attempts:
                backoff = self._backoff_base ** attempt
                await asyncio.sleep(backoff)
        last_result["attempts"] = self._max_attempts
        last_result["message"] = "Recovery failed after max attempts."
        return last_result

    async def _publish_recovery_event(
        self,
        service_name: str,
        instance_id: str,
        recovered: bool,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            await self._event_bus.publish(
                ServiceEvent(
                    event_type=ServiceEventType.REGISTRY_RECOVERED,
                    service_name=service_name,
                    instance_id=instance_id,
                    data={
                        "action": "recovery",
                        "recovered": recovered,
                    },
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to publish recovery event for '%s/%s': %s",
                service_name,
                instance_id,
                exc,
            )

    def _record_history(self, result: Dict[str, Any]) -> None:
        self._history.append(dict(result))
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ServiceRecovery(in_progress={len(self._recovering)}, "
                f"attempts={self._attempt_count})"
            )
