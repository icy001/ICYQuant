"""HA health checks for ICYQuant service discovery HA.

Provides ``HAHealth`` for performing comprehensive health
checks across all HA sub-components and returning an
aggregated health status.

Returns: {"ha_controller": True/False, "failover": True/False,
         "snapshot": True/False, "recovery": True/False,
         "cluster": True/False}
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAHealth:
    """Performs comprehensive HA health checks.

    Checks the health of registered HA components including
    the controller, failover manager, snapshot manager,
    recovery manager, and cluster state.

    Components are registered via ``register_component`` and
    checked individually or as a group via ``check``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._check_count = 0
        self._healthy_count = 0
        self._unhealthy_count = 0
        self._last_check: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def register_component(self, name: str, component: Any) -> None:
        """Register a component for health checking.

        Args:
            name: Component name (e.g., 'controller',
                'failover', 'snapshot', 'recovery', 'cluster').
            component: The component object to check.
        """
        if not name:
            raise ValueError("name cannot be empty.")
        with self._lock:
            self._components[name] = component
        logger.debug(
            "Registered component '%s' for health checks.", name
        )

    # ── Public API ──

    async def check(self) -> Dict[str, Any]:
        """Perform a full HA health check across all components.

        Returns:
            A dictionary with per-component health status
            and an overall ``healthy`` boolean.
        """
        with self._lock:
            self._check_count += 1

        results: Dict[str, Any] = {}
        results["ha_controller"] = await self.check_controller()
        results["failover"] = await self.check_failover()
        results["snapshot"] = await self.check_snapshot()
        results["recovery"] = await self.check_recovery()
        results["cluster"] = await self.check_cluster()

        all_healthy = all(
            isinstance(v, dict) and v.get("healthy", True) is not False
            for v in results.values()
        )

        results["healthy"] = all_healthy
        results["timestamp"] = self._now_iso()

        with self._lock:
            self._last_check = results
            if all_healthy:
                self._healthy_count += 1
            else:
                self._unhealthy_count += 1

        self._record_history("check", results)

        if all_healthy:
            logger.info("HA health check: all components healthy.")
        else:
            unhealthy = [
                k
                for k, v in results.items()
                if isinstance(v, dict)
                and v.get("healthy", True) is False
            ]
            logger.warning(
                "HA health check: unhealthy components: %s.",
                unhealthy,
            )

        return results

    async def check_controller(self) -> Dict[str, Any]:
        """Check the HA controller health.

        Returns:
            Health status dictionary.
        """
        result: Dict[str, Any] = {
            "component": "ha_controller",
            "healthy": True,
            "timestamp": self._now_iso(),
        }
        controller = self._components.get("controller")
        if controller is None:
            result["healthy"] = False
            result["reason"] = "not_registered"
            return result

        check_func = getattr(controller, "get_stats", None)
        if callable(check_func):
            try:
                coro = check_func()
                if asyncio.iscoroutine(coro):
                    stats = await coro
                else:
                    stats = coro
                result["stats"] = stats
            except Exception as exc:
                result["healthy"] = False
                result["reason"] = str(exc)
        return result

    async def check_failover(self) -> Dict[str, Any]:
        """Check the failover manager health.

        Returns:
            Health status dictionary.
        """
        result: Dict[str, Any] = {
            "component": "failover",
            "healthy": True,
            "timestamp": self._now_iso(),
        }
        failover = self._components.get("failover")
        if failover is None:
            result["healthy"] = False
            result["reason"] = "not_registered"
            return result

        check_func = getattr(failover, "get_stats", None)
        if callable(check_func):
            try:
                coro = check_func()
                if asyncio.iscoroutine(coro):
                    stats = await coro
                else:
                    stats = coro
                result["stats"] = stats
            except Exception as exc:
                result["healthy"] = False
                result["reason"] = str(exc)
        return result

    async def check_snapshot(self) -> Dict[str, Any]:
        """Check the snapshot manager health.

        Returns:
            Health status dictionary.
        """
        result: Dict[str, Any] = {
            "component": "snapshot",
            "healthy": True,
            "timestamp": self._now_iso(),
        }
        snapshot = self._components.get("snapshot")
        if snapshot is None:
            result["healthy"] = False
            result["reason"] = "not_registered"
            return result

        check_func = getattr(snapshot, "get_stats", None)
        if callable(check_func):
            try:
                coro = check_func()
                if asyncio.iscoroutine(coro):
                    stats = await coro
                else:
                    stats = coro
                result["stats"] = stats
            except Exception as exc:
                result["healthy"] = False
                result["reason"] = str(exc)
        return result

    async def check_recovery(self) -> Dict[str, Any]:
        """Check the recovery manager health.

        Returns:
            Health status dictionary.
        """
        result: Dict[str, Any] = {
            "component": "recovery",
            "healthy": True,
            "timestamp": self._now_iso(),
        }
        recovery = self._components.get("recovery")
        if recovery is None:
            result["healthy"] = False
            result["reason"] = "not_registered"
            return result

        check_func = getattr(recovery, "get_stats", None)
        if callable(check_func):
            try:
                coro = check_func()
                if asyncio.iscoroutine(coro):
                    stats = await coro
                else:
                    stats = coro
                result["stats"] = stats
            except Exception as exc:
                result["healthy"] = False
                result["reason"] = str(exc)
        return result

    async def check_cluster(self) -> Dict[str, Any]:
        """Check the cluster health.

        Returns:
            Health status dictionary.
        """
        result: Dict[str, Any] = {
            "component": "cluster",
            "healthy": True,
            "timestamp": self._now_iso(),
        }
        cluster = self._components.get("cluster")
        if cluster is None:
            result["healthy"] = False
            result["reason"] = "not_registered"
            return result

        check_func = getattr(cluster, "get_stats", None)
        if callable(check_func):
            try:
                coro = check_func()
                if asyncio.iscoroutine(coro):
                    stats = await coro
                else:
                    stats = coro
                result["stats"] = stats
            except Exception as exc:
                result["healthy"] = False
                result["reason"] = str(exc)
        return result

    def is_healthy(self) -> bool:
        """Return whether the last health check was healthy.

        Performs a synchronous check using the last cached
        result.  For real-time checks, use ``check()``.

        Returns:
            True if the last check was fully healthy.
        """
        with self._lock:
            if self._last_check is None:
                return False
            return bool(self._last_check.get("healthy", False))

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the health checker."""
        with self._lock:
            return {
                "check_count": self._check_count,
                "healthy_count": self._healthy_count,
                "unhealthy_count": self._unhealthy_count,
                "components": sorted(self._components.keys()),
                "last_check": (
                    {
                        "healthy": self._last_check.get("healthy"),
                        "timestamp": self._last_check.get(
                            "timestamp"
                        ),
                    }
                    if self._last_check
                    else None
                ),
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAHealth(components={len(self._components)}, "
                f"checks={self._check_count})"
            )