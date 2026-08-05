"""Liveness probe for ICYQuant service discovery.

Provides ``LivenessProbe`` for determining whether a service is
alive and not in a stuck/deadlocked state. A liveness failure
indicates the service should be restarted. Checks cover Deadlock,
Memory, Thread, Event Loop, and Heartbeat health.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ServiceDiscoveryError

logger = logging.getLogger(__name__)


class LivenessProbe:
    """Probe for determining service liveness.

    Aggregates a set of named liveness checks. A failure of any
    check indicates the service is unhealthy and should be restarted.

    Args:
        checks: Optional initial list of (name, check_fn) tuples.
    """

    DEFAULT_CHECKS = (
        "deadlock",
        "memory",
        "thread",
        "event_loop",
        "heartbeat",
    )

    def __init__(self, checks: Optional[List[Callable]] = None) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, bool] = {}
        self._last_run_ts: float = 0.0
        self._last_alive: bool = True
        self._exec_count = 0
        self._failure_count = 0
        if checks:
            for idx, check_fn in enumerate(checks):
                name = getattr(check_fn, "__name__", None) or f"check_{idx}"
                self.add_check(name, check_fn)

    # ── Public API ──

    def add_check(self, name: str, check_fn: Callable) -> None:
        """Register a liveness check under ``name``.

        Args:
            name: Check name.
            check_fn: Callable returning a bool or awaitable bool.
        """
        if not name:
            raise ServiceDiscoveryError("Check name must be non-empty.")
        if not callable(check_fn):
            raise ServiceDiscoveryError("Check must be callable.")
        with self._lock:
            self._checks[name] = check_fn
        logger.debug("Registered liveness check '%s'.", name)

    async def execute(self, target: str = None) -> Dict[str, Any]:
        """Execute all liveness checks.

        Args:
            target: Ignored; present for ``Probe`` interface
                compatibility.

        Returns:
            A dictionary describing the liveness outcome.
        """
        start = time.monotonic()
        with self._lock:
            checks = list(self._checks.items())
        results: Dict[str, bool] = {}
        errors: Dict[str, str] = {}
        for name, check_fn in checks:
            try:
                result = check_fn()
                if inspect.isawaitable(result):
                    result = await result
                results[name] = bool(result)
            except Exception as exc:
                results[name] = False
                errors[name] = str(exc)
                logger.warning(
                    "Liveness check '%s' failed: %s", name, exc
                )
        alive = bool(results) and all(results.values())
        latency = time.monotonic() - start
        with self._lock:
            self._last_results = dict(results)
            self._last_run_ts = time.time()
            self._last_alive = alive
            self._exec_count += 1
            if not alive:
                self._failure_count += 1
        if not alive:
            logger.error(
                "Liveness check failed; service restart may be required: %s",
                errors,
            )
        return {
            "alive": alive,
            "status": "alive" if alive else "dead",
            "latency_ms": latency * 1000.0,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results,
            "errors": errors,
            "message": (
                "All liveness checks passed."
                if alive
                else "One or more liveness checks failed."
            ),
        }

    def is_alive(self) -> bool:
        """Return whether the last execution reported alive."""
        with self._lock:
            return self._last_alive

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the liveness probe."""
        with self._lock:
            return {
                "check_count": len(self._checks),
                "check_names": list(self._checks.keys()),
                "exec_count": self._exec_count,
                "failure_count": self._failure_count,
                "last_alive": self._last_alive,
                "last_run_ts": self._last_run_ts,
                "last_results": dict(self._last_results),
                "python_version": sys.version.split()[0],
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"LivenessProbe(checks={len(self._checks)}, "
                f"alive={self._last_alive})"
            )
