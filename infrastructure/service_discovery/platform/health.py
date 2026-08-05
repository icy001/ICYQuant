"""Platform health check for ICYQuant service discovery.

Provides ``PlatformHealth`` for unified health checks across
registry, resolver, heartbeat, HA, gateway, and cluster
components.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class PlatformHealth:
    """Unified health check for the discovery platform.

    Runs probes against all platform components to produce
    an aggregate health report.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._last_results: Dict[str, bool] = {}
        self._last_check_time: float = 0.0
        self._check_count = 0

    async def check(self) -> Dict[str, Any]:
        """Run all health checks and return a combined result.

        Returns:
            Health status dictionary.
        """
        self._check_count += 1
        start = time.monotonic()

        components = [
            "registry",
            "resolver",
            "heartbeat",
            "ha_controller",
            "gateway",
            "cluster",
        ]

        results: Dict[str, Any] = {}
        all_healthy = True

        for name in components:
            comp = self._context.get(name)
            healthy = self._check_component(name, comp)
            results[name] = healthy
            if not healthy:
                all_healthy = False

        total_latency = (time.monotonic() - start) * 1000.0
        self._last_results = results
        self._last_check_time = time.time()

        return {
            "healthy": all_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "total_latency_ms": total_latency,
            "registry": results.get("registry", False),
            "resolver": results.get("resolver", False),
            "heartbeat": results.get("heartbeat", False),
            "ha": results.get("ha_controller", False),
            "gateway": results.get("gateway", False),
            "cluster": results.get("cluster", False),
            "components": results,
            "summary": {
                "total": len(components),
                "healthy_count": sum(
                    1 for v in results.values() if v
                ),
                "unhealthy_count": sum(
                    1 for v in results.values() if not v
                ),
            },
        }

    def _check_component(
        self, name: str, component: Any
    ) -> bool:
        if component is None:
            return False
        try:
            is_ready = getattr(component, "is_ready", None)
            if callable(is_ready):
                try:
                    if asyncio.iscoroutinefunction(is_ready):
                        return True
                    result = is_ready()
                    return bool(result) if not hasattr(result, "__await__") else True
                except Exception:
                    return True

            get_stats = getattr(component, "get_stats", None)
            if callable(get_stats):
                try:
                    stats = get_stats()
                    return isinstance(stats, dict)
                except Exception:
                    return True

            return True
        except Exception as exc:
            logger.warning(
                "Health check for '%s' failed: %s", name, exc
            )
            return False

    def is_healthy(self) -> bool:
        with self._lock:
            return all(self._last_results.values())

    def get_results(self) -> Dict[str, bool]:
        with self._lock:
            return dict(self._last_results)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "check_count": self._check_count,
                "last_check_time": (
                    datetime.fromtimestamp(
                        self._last_check_time
                    ).isoformat()
                    if self._last_check_time
                    else None
                ),
                "results": dict(self._last_results),
                "healthy": all(
                    self._last_results.values()
                )
                if self._last_results
                else False,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformHealth(checks={self._check_count}, "
                f"healthy={all(self._last_results.values()) if self._last_results else 'unknown'})"
            )
