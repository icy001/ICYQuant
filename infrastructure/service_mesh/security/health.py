"""Security health checks for ICYQuant Service Mesh.

Provides ``SecurityHealth`` for monitoring the health of security
components including CA, certificate manager, identity service,
mTLS engine, and policy engine.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityHealth:
    """Health check manager for security components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable[[], bool]] = {}
        self._check_results: Dict[str, Dict[str, Any]] = {}
        self._last_check_time: Optional[float] = None

    def register_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        with self._lock:
            self._checks[name] = check_fn

    def unregister_check(self, name: str) -> bool:
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                self._check_results.pop(name, None)
                return True
            return False

    async def check(self) -> Dict[str, Any]:
        with self._lock:
            checks = dict(self._checks)

        components: Dict[str, bool] = {}
        unhealthy_count = 0

        for name, check_fn in checks.items():
            try:
                healthy = bool(check_fn())
                components[name] = healthy
                if not healthy:
                    unhealthy_count += 1
                with self._lock:
                    self._check_results[name] = {
                        "healthy": healthy,
                        "timestamp": time.monotonic(),
                    }
            except Exception as exc:
                components[name] = False
                unhealthy_count += 1
                logger.warning("Security health check '%s' failed: %s", name, exc)
                with self._lock:
                    self._check_results[name] = {
                        "healthy": False,
                        "error": str(exc),
                        "timestamp": time.monotonic(),
                    }

        self._last_check_time = time.monotonic()
        return {
            "healthy": unhealthy_count == 0,
            "components": components,
            "unhealthy_count": unhealthy_count,
            "timestamp": self._last_check_time,
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "check_count": len(self._checks),
                "last_check_time": self._last_check_time,
                "results": dict(self._check_results),
            }
