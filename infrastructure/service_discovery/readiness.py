"""Readiness probe for ICYQuant service discovery.

Provides ``ReadinessProbe`` for determining whether a service is
ready to receive traffic. A service is considered ready only when
all registered dependency checks (e.g. Database, Redis, Kafka,
Configuration, Secrets, Dependencies) pass.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ServiceDiscoveryError

logger = logging.getLogger(__name__)


class ReadinessProbe:
    """Probe for determining service readiness.

    Aggregates a set of named dependency checks. The probe reports
    ``ready=True`` only when every check returns truthy.

    Args:
        checks: Optional initial list of (name, check_fn) tuples.
    """

    DEFAULT_CHECKS = (
        "database",
        "redis",
        "kafka",
        "configuration",
        "secrets",
        "dependencies",
    )

    def __init__(self, checks: Optional[List[Callable]] = None) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, bool] = {}
        self._last_run_ts: float = 0.0
        self._last_ready: bool = False
        self._exec_count = 0
        if checks:
            for idx, check_fn in enumerate(checks):
                name = getattr(check_fn, "__name__", None) or f"check_{idx}"
                self.add_check(name, check_fn)

    # ── Public API ──

    def add_check(self, name: str, check_fn: Callable) -> None:
        """Register a readiness check under ``name``.

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
        logger.debug("Registered readiness check '%s'.", name)

    def remove_check(self, name: str) -> None:
        """Remove a readiness check by name."""
        with self._lock:
            self._checks.pop(name, None)
            self._last_results.pop(name, None)
        logger.debug("Removed readiness check '%s'.", name)

    async def execute(self, target: str = None) -> Dict[str, Any]:
        """Execute all readiness checks.

        Args:
            target: Ignored; present for ``Probe`` interface
                compatibility.

        Returns:
            A dictionary describing the readiness outcome.
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
                    "Readiness check '%s' failed: %s", name, exc
                )
        ready = bool(results) and all(results.values())
        latency = time.monotonic() - start
        with self._lock:
            self._last_results = dict(results)
            self._last_run_ts = time.time()
            self._last_ready = ready
            self._exec_count += 1
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "latency_ms": latency * 1000.0,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results,
            "errors": errors,
            "message": (
                "All readiness checks passed."
                if ready
                else "One or more readiness checks failed."
            ),
        }

    def is_ready(self) -> bool:
        """Return whether the last execution reported ready."""
        with self._lock:
            return self._last_ready

    def get_checks(self) -> Dict[str, bool]:
        """Return the latest per-check results."""
        with self._lock:
            return dict(self._last_results)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the readiness probe."""
        with self._lock:
            return {
                "check_count": len(self._checks),
                "check_names": list(self._checks.keys()),
                "exec_count": self._exec_count,
                "last_ready": self._last_ready,
                "last_run_ts": self._last_run_ts,
                "last_results": dict(self._last_results),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ReadinessProbe(checks={len(self._checks)}, "
                f"ready={self._last_ready})"
            )
