"""Readiness Probe.

Kubernetes-style readiness/liveness probes for ICYQuant services.
Supports startup, liveness, and readiness probes.

Usage::

    probe = ReadinessProbe()
    probe.add_check(ProbeType.LIVENESS, "api", check_fn)
    result = probe.run(ProbeType.LIVENESS)
    print(result.ready)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class ProbeType(str, Enum):
    STARTUP = "startup"
    LIVENESS = "liveness"
    READINESS = "readiness"


@dataclass
class ReadinessResult:
    """Result of running a set of probes."""

    probe_type: ProbeType
    ready: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        from typing import Any
        return {
            "probe_type": self.probe_type.value,
            "ready": self.ready,
            "checks": self.checks,
            "failures": self.failures,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
        }


class ReadinessProbe:
    """Manages liveness, readiness, and startup probes.

    Typical probe types:
    - startup: checks if the process has started (initial phase)
    - liveness: checks if the process is still alive
    - readiness: checks if the process is ready to serve traffic
    """

    def __init__(self, failure_threshold: int = 3) -> None:
        self._probes: Dict[ProbeType, Dict[str, Callable[[], bool]]] = {
            ProbeType.STARTUP: {},
            ProbeType.LIVENESS: {},
            ProbeType.READINESS: {},
        }
        self._failure_counts: Dict[str, int] = {}
        self._failure_threshold = failure_threshold
        self._start_time: Optional[float] = None

    def mark_started(self) -> None:
        """Mark the application as started."""
        self._start_time = time.time()

    def add_check(
        self,
        probe_type: ProbeType,
        name: str,
        check_fn: Callable[[], bool],
    ) -> None:
        """Add a check function for a probe type."""
        self._probes[probe_type][name] = check_fn
        self._failure_counts.setdefault(f"{probe_type.value}:{name}", 0)

    def run(self, probe_type: ProbeType) -> ReadinessResult:
        """Run all checks for a given probe type."""
        start = time.time()
        checks = self._probes[probe_type]
        results: Dict[str, bool] = {}
        failures: List[str] = []

        for name, check_fn in checks.items():
            key = f"{probe_type.value}:{name}"
            try:
                ok = check_fn()
                if ok:
                    self._failure_counts[key] = 0
                else:
                    self._failure_counts[key] += 1
            except Exception:
                ok = False
                self._failure_counts[key] += 1

            results[name] = ok
            if not ok:
                failures.append(name)

        ready = len(failures) == 0
        duration = (time.time() - start) * 1000.0

        # If any check has exceeded failure threshold, mark as not ready
        for name in failures:
            key = f"{probe_type.value}:{name}"
            if self._failure_counts[key] >= self._failure_threshold:
                # Persistent failure - don't flip-flop
                pass

        return ReadinessResult(
            probe_type=probe_type,
            ready=ready,
            checks=results,
            failures=failures,
            duration_ms=duration,
        )

    def is_ready(self) -> bool:
        """Check if the application is ready to serve traffic."""
        return self.run(ProbeType.READINESS).ready

    def is_alive(self) -> bool:
        """Check if the application is alive."""
        return self.run(ProbeType.LIVENESS).ready

    def startup_complete(self) -> bool:
        """Check if startup is complete."""
        return self.run(ProbeType.STARTUP).ready

    def uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time
