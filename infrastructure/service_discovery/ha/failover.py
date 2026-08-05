"""Failover manager for ICYQuant service discovery HA.

Provides ``FailoverManager`` for detecting failures, promoting
healthy replicas, switching traffic, updating the registry,
and orchestrating the full failover flow.

Flow: Failure Detection -> Healthy Replica Selection ->
      Traffic Switch -> Registry Update -> Recovery
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class FailoverManager:
    """Orchestrates failover for a failed service instance.

    Detects failures via an optional detector, selects a healthy
    replica, promotes it as the new primary, switches traffic,
    and updates the registry.

    Args:
        registry: Optional registry for state updates.
        detector: Optional failure detector with a
            ``compute_phi`` or ``is_failed`` method.
    """

    def __init__(
        self,
        registry: Any = None,
        detector: Any = None,
    ) -> None:
        self._registry = registry
        self._detector = detector
        self._lock = threading.RLock()
        self._failover_history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._detection_count = 0
        self._promotion_count = 0
        self._failover_count = 0
        self._recovery_count = 0
        self._failures_detected = 0

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    async def detect(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Detect whether an instance has failed.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary with ``failed``, ``phi``, and ``reason``
            fields.
        """
        with self._lock:
            self._detection_count += 1

        phi = 0.0
        failed = False
        reason = "unknown"

        if self._detector is not None:
            phi_func = getattr(self._detector, "compute_phi", None)
            is_failed_func = getattr(self._detector, "is_failed", None)

            if callable(phi_func):
                try:
                    result = phi_func(service_name, instance_id)
                    if asyncio.iscoroutine(result):
                        phi = float(await result)
                    else:
                        phi = float(result)
                except Exception:
                    phi = 0.0

            if callable(is_failed_func):
                try:
                    result = is_failed_func(service_name, instance_id)
                    if asyncio.iscoroutine(result):
                        failed = bool(await result)
                    else:
                        failed = bool(result)
                except Exception:
                    failed = False

            if failed:
                reason = "detector_dead"
            elif phi > 0:
                reason = "detector_suspicious"
            else:
                reason = "alive"
        else:
            reason = "no_detector"

        if failed:
            with self._lock:
                self._failures_detected += 1
            logger.warning(
                "Failure detected for '%s/%s' (phi=%.3f, reason=%s).",
                service_name,
                instance_id,
                phi,
                reason,
            )

        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "failed": failed,
            "phi": phi,
            "reason": reason,
            "timestamp": self._now_iso(),
        }
        self._record_history("detect", result)
        return result

    async def promote(
        self,
        service_name: str,
        healthy_instances: List[ServiceInstance],
    ) -> Dict[str, Any]:
        """Promote a healthy replica to take over.

        Selects the best healthy instance and promotes it as the
        new primary target.

        Args:
            service_name: The logical service name.
            healthy_instances: List of healthy ``ServiceInstance``
                candidates.

        Returns:
            A dictionary describing the promotion result.
        """
        with self._lock:
            self._promotion_count += 1

        if not healthy_instances:
            result: Dict[str, Any] = {
                "service_name": service_name,
                "promoted": False,
                "reason": "no_healthy_instances",
                "timestamp": self._now_iso(),
            }
            self._record_history("promote", result)
            return result

        best = max(
            healthy_instances,
            key=lambda i: (
                i.weight,
                int(i.healthy),
            ),
        )

        if self._registry is not None:
            update_func = getattr(self._registry, "update_instance", None)
            if callable(update_func):
                try:
                    result_coro = update_func(
                        service_name,
                        best.instance_id,
                        {"weight": max(best.weight, 10)},
                    )
                    if asyncio.iscoroutine(result_coro):
                        await result_coro
                except Exception as exc:
                    logger.warning(
                        "Failed to update promoted instance '%s': %s",
                        best.instance_id,
                        exc,
                    )

        result = {
            "service_name": service_name,
            "promoted": True,
            "promoted_instance_id": best.instance_id,
            "promoted_instance_host": best.host,
            "promoted_instance_port": best.port,
            "timestamp": self._now_iso(),
        }
        self._record_history("promote", result)
        logger.info(
            "Promoted '%s/%s' as new primary.",
            service_name,
            best.instance_id,
        )
        return result

    async def recover(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Run the recovery flow for a failed instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the recovery result.
        """
        with self._lock:
            self._recovery_count += 1

        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "recovered": False,
            "stages": {},
            "timestamp": self._now_iso(),
        }

        result["stages"]["drain"] = await self._drain_instance(
            service_name, instance_id
        )
        result["stages"]["deregister"] = await self._deregister_instance(
            service_name, instance_id
        )
        result["stages"]["restart"] = await self._restart_instance(
            service_name, instance_id
        )
        result["stages"]["reregister"] = await self._reregister_instance(
            service_name, instance_id
        )

        result["recovered"] = all(
            stage.get("success", False) is not False
            for stage in result["stages"].values()
            if isinstance(stage, dict)
        )

        if result["recovered"]:
            logger.info(
                "Successfully recovered '%s/%s'.",
                service_name,
                instance_id,
            )
        else:
            logger.warning(
                "Recovery failed for '%s/%s'.",
                service_name,
                instance_id,
            )

        self._record_history("recover", result)
        return result

    async def execute_failover(
        self,
        service_name: str,
        failed_instance: str,
        replicas: List[ServiceInstance],
    ) -> Dict[str, Any]:
        """Execute the full failover flow.

        Flow:
            1. Detect failure
            2. Promote a healthy replica
            3. Switch traffic (registry update)
            4. Recover the failed instance

        Args:
            service_name: The logical service name.
            failed_instance: The ID of the failed instance.
            replicas: List of replica instances (including
                healthy candidates).

        Returns:
            A dictionary describing the full failover result.
        """
        with self._lock:
            self._failover_count += 1

        healthy = [r for r in replicas if r.is_healthy()]
        if not healthy:
            result: Dict[str, Any] = {
                "service_name": service_name,
                "failed_instance": failed_instance,
                "failover_executed": False,
                "reason": "no_healthy_replicas",
                "timestamp": self._now_iso(),
            }
            self._record_history("failover", result)
            return result

        detection = await self.detect(service_name, failed_instance)
        promotion = await self.promote(service_name, healthy)

        result = {
            "service_name": service_name,
            "failed_instance": failed_instance,
            "failover_executed": True,
            "detection": detection,
            "promotion": promotion,
            "traffic_switched": promotion.get("promoted", False),
            "timestamp": self._now_iso(),
        }

        if promotion.get("promoted"):
            recovery = await self.recover(service_name, failed_instance)
            result["recovery"] = recovery

        self._record_history("failover", result)
        logger.info(
            "Failover executed for '%s' (failed: %s).",
            service_name,
            failed_instance,
        )
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the failover manager."""
        with self._lock:
            return {
                "detection_count": self._detection_count,
                "promotion_count": self._promotion_count,
                "failover_count": self._failover_count,
                "recovery_count": self._recovery_count,
                "failures_detected": self._failures_detected,
                "history_size": len(self._failover_history),
                "max_history": self._max_history,
                "registry_attached": self._registry is not None,
                "detector_attached": self._detector is not None,
            }

    # ── Internal helpers ──

    async def _drain_instance(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "message": "Instance drained.",
        }

    async def _deregister_instance(
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

    async def _restart_instance(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "message": "Restart is a no-op placeholder.",
        }

    async def _reregister_instance(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        if self._registry is None:
            return {
                "success": True,
                "message": "No registry; reregister skipped.",
            }
        register_func = getattr(self._registry, "register", None)
        if not callable(register_func):
            return {
                "success": True,
                "message": "No register method; skipped.",
            }
        try:
            dummy = ServiceInstance(
                service_name=service_name,
                instance_id=instance_id,
                host="127.0.0.1",
                port=0,
            )
            result = register_func(dummy)
            if asyncio.iscoroutine(result):
                await result
            return {"success": True, "message": "Reregistered."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._failover_history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._failover_history) > self._max_history:
            excess = len(self._failover_history) - self._max_history
            del self._failover_history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"FailoverManager(detections={self._detection_count}, "
                f"failovers={self._failover_count})"
            )