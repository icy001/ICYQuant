"""Health check for the Service Mesh.

Provides ``MeshHealth`` for unified health checking of all
mesh components: control plane, data plane, sidecar, proxy,
and configuration.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MeshHealth:
    """Unified health check for the service mesh."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._checks = {
            "control_plane": lambda: True,
            "data_plane": lambda: True,
            "sidecar": lambda: True,
            "proxy": lambda: True,
            "configuration": lambda: True,
        }

    def register_check(
        self,
        name: str,
        check_fn: Callable,
    ) -> None:
        with self._lock:
            self._checks[name] = check_fn

    def unregister_check(self, name: str) -> None:
        with self._lock:
            self._checks.pop(name, None)

    async def check(
        self, component: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run health checks for components."""
        with self._lock:
            checks_to_run = (
                {k: v for k, v in self._checks.items()}
                if component is None
                else {
                    k: v
                    for k, v in self._checks.items()
                    if k == component
                }
            )

        results: Dict[str, bool] = {}
        component_details: Dict[str, Any] = {}

        for name, check_fn in checks_to_run.items():
            try:
                coro = check_fn()
                if asyncio.iscoroutine(coro):
                    result = await asyncio.wait_for(coro, timeout=5.0)
                else:
                    result = coro
                if isinstance(result, dict):
                    results[name] = result.get("healthy", True)
                    component_details[name] = result
                else:
                    results[name] = bool(result)
                    component_details[name] = {
                        "healthy": bool(result)
                    }
            except Exception as exc:
                results[name] = False
                component_details[name] = {
                    "healthy": False,
                    "error": str(exc),
                }

        all_healthy = all(results.values()) if results else True

        check_result: Dict[str, Any] = {
            "healthy": all_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "components": results,
            "details": component_details,
            "total": len(results),
            "healthy_count": sum(1 for v in results.values() if v),
            "unhealthy_count": sum(
                1 for v in results.values() if not v
            ),
        }

        self._add_to_history(check_result)
        return check_result

    async def check_component(self, name: str) -> Dict[str, Any]:
        """Check a single component's health."""
        return await self.check(component=name)

    def _add_to_history(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])

    def get_unhealthy_components(self) -> List[str]:
        """Get list of currently unhealthy component names."""
        if not self._history:
            return []
        last = self._history[-1]
        return [
            name
            for name, healthy in last.get("components", {}).items()
            if not healthy
        ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "registered_checks": list(self._checks.keys()),
                "history_size": len(self._history),
                "last_check": self._history[-1]
                if self._history
                else None,
            }
