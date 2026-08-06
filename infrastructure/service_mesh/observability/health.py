"""Health checking for the observability platform.

Provides ``ObservabilityHealth`` for monitoring component health
across all observability subsystems.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObservabilityHealth:
    """Health check manager for observability components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, Dict[str, Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._checks = {
            "trace_collector": lambda: True,
            "metrics_collector": lambda: True,
            "log_pipeline": lambda: True,
            "policy_evaluator": lambda: True,
            "runtime_analyzer": lambda: True,
            "anomaly_detector": lambda: True,
            "slo_monitor": lambda: True,
            "dashboard": lambda: True,
        }

    def register_check(
        self, name: str, check_fn: Callable
    ) -> None:
        with self._lock:
            self._checks[name] = check_fn

    def unregister_check(self, name: str) -> bool:
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                return True
            return False

    async def check(
        self, component: Optional[str] = None
    ) -> Dict[str, Any]:
        import asyncio

        with self._lock:
            checks_to_run = (
                dict(self._checks)
                if component is None
                else {
                    k: v
                    for k, v in self._checks.items()
                    if k == component
                }
            )

        results: Dict[str, bool] = {}
        details: Dict[str, Dict[str, Any]] = {}

        for name, check_fn in checks_to_run.items():
            try:
                coro = check_fn()
                if asyncio.iscoroutine(coro):
                    result = await asyncio.wait_for(coro, timeout=5.0)
                else:
                    result = coro

                healthy = bool(result)
                if isinstance(result, dict):
                    healthy = bool(result.get("healthy", False))
                    details[name] = result
                else:
                    details[name] = {"healthy": healthy}
                results[name] = healthy
            except Exception as exc:
                results[name] = False
                details[name] = {
                    "healthy": False,
                    "error": str(exc),
                }

        all_healthy = all(results.values()) if results else False

        result = {
            "healthy": all_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "components": results,
            "details": details,
            "total": len(results),
            "healthy_count": sum(1 for v in results.values() if v),
            "unhealthy_count": sum(1 for v in results.values() if not v),
        }

        with self._lock:
            self._last_results = result
        return result

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "check_count": len(self._checks),
                "last_healthy": self._last_results.get("healthy", False),
                "last_check_time": self._last_results.get("timestamp"),
            }
