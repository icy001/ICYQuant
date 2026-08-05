"""Startup probe for ICYQuant service discovery.

Provides ``StartupProbe`` for services with slow initialization
(model loading, broker login, large cache warm-up). While the probe
has not yet reported ``started``, liveness/readiness checks are
suppressed to avoid false failure detection during startup.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ServiceDiscoveryError

logger = logging.getLogger(__name__)


class StartupProbe:
    """Probe for tracking slow service startup.

    Tracks whether the service has completed initialization within
    the configured timeout window. Callers should periodically invoke
    :meth:`execute` until ``is_started`` returns True.

    Args:
        timeout: Maximum allowed startup duration in seconds.
        check_interval: Interval between startup checks in seconds.
        checks: Optional list of startup check callables.
    """

    def __init__(
        self,
        timeout: float = 300.0,
        check_interval: float = 5.0,
        checks: Optional[List[Callable]] = None,
    ) -> None:
        self._timeout = float(timeout) if timeout > 0 else 300.0
        self._check_interval = (
            float(check_interval) if check_interval > 0 else 5.0
        )
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable] = {}
        self._started = False
        self._start_ts: float = time.time()
        self._completed_ts: float = 0.0
        self._exec_count = 0
        self._failure_count = 0
        self._last_results: Dict[str, bool] = {}
        self._mark_started = False
        if checks:
            for idx, check_fn in enumerate(checks):
                name = getattr(check_fn, "__name__", None) or f"check_{idx}"
                self.add_check(name, check_fn)

    # ── Public API ──

    def add_check(self, name: str, check_fn: Callable) -> None:
        """Register a startup check under ``name``."""
        if not name:
            raise ServiceDiscoveryError("Check name must be non-empty.")
        if not callable(check_fn):
            raise ServiceDiscoveryError("Check must be callable.")
        with self._lock:
            self._checks[name] = check_fn

    async def execute(self, target: str = None) -> Dict[str, Any]:
        """Execute startup checks.

        Returns ``started=True`` when all checks pass or when
        :meth:`mark_started` was called. Returns ``timed_out=True``
        when the timeout has elapsed without completion.

        Args:
            target: Ignored; present for ``Probe`` interface
                compatibility.

        Returns:
            A dictionary describing the startup state.
        """
        start = time.monotonic()
        with self._lock:
            already_started = self._started
            mark_started = self._mark_started
            checks = list(self._checks.items())
            elapsed = time.time() - self._start_ts
        self._exec_count += 1

        if already_started:
            return self._build_result(
                started=True,
                timed_out=False,
                message="Startup already complete.",
                latency=time.monotonic() - start,
                results={},
            )

        if mark_started:
            self._complete()
            return self._build_result(
                started=True,
                timed_out=False,
                message="Startup marked complete.",
                latency=time.monotonic() - start,
                results={},
            )

        results: Dict[str, bool] = {}
        errors: Dict[str, str] = {}
        for name, check_fn in checks:
            try:
                result = check_fn()
                if asyncio.iscoroutine(result):
                    result = await result
                results[name] = bool(result)
            except Exception as exc:
                results[name] = False
                errors[name] = str(exc)
                logger.warning(
                    "Startup check '%s' failed: %s", name, exc
                )

        all_passed = bool(results) and all(results.values())
        timed_out = elapsed >= self._timeout
        with self._lock:
            self._last_results = dict(results)
            if not all_passed:
                self._failure_count += 1

        if all_passed:
            self._complete()
            return self._build_result(
                started=True,
                timed_out=False,
                message="All startup checks passed.",
                latency=time.monotonic() - start,
                results=results,
                errors=errors,
            )

        return self._build_result(
            started=False,
            timed_out=timed_out,
            message=(
                "Startup timed out before checks passed."
                if timed_out
                else "Startup checks not yet passing."
            ),
            latency=time.monotonic() - start,
            results=results,
            errors=errors,
        )

    def is_started(self) -> bool:
        """Return whether startup has completed."""
        with self._lock:
            return self._started

    def mark_started(self) -> None:
        """Mark startup as complete without running checks."""
        with self._lock:
            self._mark_started = True
        self._complete()

    def reset(self) -> None:
        """Reset the probe to its initial state."""
        with self._lock:
            self._started = False
            self._mark_started = False
            self._start_ts = time.time()
            self._completed_ts = 0.0
            self._exec_count = 0
            self._failure_count = 0
            self._last_results.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the startup probe."""
        with self._lock:
            elapsed = (
                (self._completed_ts - self._start_ts)
                if self._started and self._completed_ts
                else (time.time() - self._start_ts)
            )
            return {
                "started": self._started,
                "timeout": self._timeout,
                "check_interval": self._check_interval,
                "check_count": len(self._checks),
                "check_names": list(self._checks.keys()),
                "exec_count": self._exec_count,
                "failure_count": self._failure_count,
                "elapsed_seconds": elapsed,
                "last_results": dict(self._last_results),
            }

    # ── Internal helpers ──

    def _complete(self) -> None:
        with self._lock:
            if not self._started:
                self._started = True
                self._completed_ts = time.time()
                logger.info(
                    "Startup complete after %.2fs.",
                    self._completed_ts - self._start_ts,
                )

    def _build_result(
        self,
        started: bool,
        timed_out: bool,
        message: str,
        latency: float,
        results: Dict[str, bool],
        errors: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "started": started,
            "timed_out": timed_out,
            "status": (
                "started"
                if started
                else ("timed_out" if timed_out else "starting")
            ),
            "latency_ms": latency * 1000.0,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "checks": results,
            "errors": errors or {},
        }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"StartupProbe(started={self._started}, "
                f"checks={len(self._checks)})"
            )
