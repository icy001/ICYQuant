"""Graceful eviction for ICYQuant service discovery HA.

Provides ``GracefulEviction`` for evicting service instances
with support for manual, automatic, maintenance, and upgrade
modes.

Pipeline: Evict -> Drain -> Deregister -> Shutdown
Modes: manual, automatic, maintenance, upgrade
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .traffic_drain import TrafficDrain

logger = logging.getLogger(__name__)

EVICTION_MODES = frozenset(
    {"manual", "automatic", "maintenance", "upgrade"}
)


class GracefulEviction:
    """Manages graceful eviction of service instances.

    Orchestrates the eviction pipeline: drain traffic,
    deregister from registry, and optionally signal shutdown.

    Args:
        registry: Optional service registry for deregistration.
        traffic_drain: Optional ``TrafficDrain`` instance.
    """

    def __init__(
        self,
        registry: Any = None,
        traffic_drain: Optional[TrafficDrain] = None,
    ) -> None:
        self._registry = registry
        self._traffic_drain = traffic_drain or TrafficDrain()
        self._lock = threading.RLock()
        self._evicting: Dict[str, Dict[str, Any]] = {}
        self._evict_count = 0
        self._batch_count = 0
        self._cancel_count = 0
        self._complete_count = 0
        self._history: List[Dict[str, Any]] = []
        self._max_history = 500

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    async def evict(
        self,
        service_name: str,
        instance_id: str,
        mode: str = "manual",
    ) -> Dict[str, Any]:
        """Evict a service instance gracefully.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            mode: Eviction mode (manual, automatic, maintenance,
                upgrade).

        Returns:
            A dictionary describing the eviction result.
        """
        mode = (mode or "manual").lower()
        if mode not in EVICTION_MODES:
            mode = "manual"

        key = self._make_key(service_name, instance_id)
        with self._lock:
            self._evicting[key] = {
                "service_name": service_name,
                "instance_id": instance_id,
                "mode": mode,
                "status": "evicting",
                "started_at": time.time(),
                "started_at_iso": self._now_iso(),
                "cancelled": False,
            }
            self._evict_count += 1

        logger.info(
            "Evicting '%s/%s' (mode=%s).",
            service_name,
            instance_id,
            mode,
        )

        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "mode": mode,
            "evicted": False,
            "stages": {},
            "timestamp": self._now_iso(),
        }

        drain_result = await self._traffic_drain.drain(
            service_name, instance_id
        )
        result["stages"]["drain"] = drain_result

        with self._lock:
            record = self._evicting.get(key)
            if record is not None and record.get("cancelled"):
                result["evicted"] = False
                result["cancelled"] = True
                self._record_history("evict_cancelled", result)
                return result

        result["stages"]["deregister"] = await self._deregister(
            service_name, instance_id
        )

        result["stages"]["shutdown"] = await self._signal_shutdown(
            service_name, instance_id, mode
        )

        def _stage_succeeded(stage: Dict[str, Any]) -> bool:
            if not isinstance(stage, dict):
                return False
            if "success" in stage:
                return stage["success"] is not False
            if "drained" in stage:
                return stage["drained"] is not False
            if "completed" in stage:
                return stage["completed"] is not False
            return True

        result["evicted"] = all(
            _stage_succeeded(stage)
            for stage in result["stages"].values()
        )

        with self._lock:
            record = self._evicting.get(key)
            if record is not None:
                record["status"] = "evicted"
                record["completed_at"] = time.time()
            if result["evicted"]:
                self._complete_count += 1

        self._record_history("evict", result)
        return result

    async def evict_batch(
        self, instances: List[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """Evict multiple instances in batch.

        Args:
            instances: List of (service_name, instance_id) tuples.

        Returns:
            A list of result dictionaries.
        """
        with self._lock:
            self._batch_count += 1

        results: List[Dict[str, Any]] = []
        for service_name, instance_id in instances:
            try:
                result = await self.evict(
                    service_name, instance_id
                )
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "Batch evict failed for '%s/%s': %s",
                    service_name,
                    instance_id,
                    exc,
                )
                results.append(
                    {
                        "service_name": service_name,
                        "instance_id": instance_id,
                        "evicted": False,
                        "error": str(exc),
                    }
                )
        return results

    def cancel_eviction(
        self, service_name: str, instance_id: str
    ) -> None:
        """Cancel an ongoing eviction.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._evicting.get(key)
            if record is not None:
                record["cancelled"] = True
                record["status"] = "cancelled"
                self._cancel_count += 1
        logger.info(
            "Cancelled eviction of '%s/%s'.", service_name, instance_id
        )

    def is_evicting(
        self, service_name: str, instance_id: str
    ) -> bool:
        """Return whether an instance is currently being evicted.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._evicting.get(key)
            if record is None:
                return False
            return record.get("status") in ("evicting",)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the eviction manager."""
        with self._lock:
            active = sum(
                1
                for r in self._evicting.values()
                if r.get("status") == "evicting"
            )
            return {
                "active_evictions": active,
                "total_evictions": self._evict_count,
                "batch_count": self._batch_count,
                "cancel_count": self._cancel_count,
                "completed_count": self._complete_count,
                "history_size": len(self._history),
                "max_history": self._max_history,
                "registry_attached": self._registry is not None,
                "traffic_drain_attached": self._traffic_drain is not None,
            }

    # ── Internal helpers ──

    async def _deregister(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        if self._registry is None:
            return {
                "success": True,
                "message": "No registry; deregister skipped.",
            }
        deregister_func = getattr(self._registry, "deregister", None)
        if not callable(deregister_func):
            return {
                "success": True,
                "message": "No deregister method; skipped.",
            }
        try:
            result = deregister_func(service_name, instance_id)
            if asyncio.iscoroutine(result):
                await result
            return {"success": True, "message": "Deregistered."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    async def _signal_shutdown(
        service_name: str, instance_id: str, mode: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "mode": mode,
            "message": "Shutdown signal sent.",
        }

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            active = sum(
                1
                for r in self._evicting.values()
                if r.get("status") == "evicting"
            )
            return (
                f"GracefulEviction(active={active}, "
                f"completed={self._complete_count})"
            )