"""Dependency Health Checker.

Checks health of external dependencies:
- Redis, Kafka, Postgres, Broker Gateway
- EventBus internal health
- External API availability

Usage::

    checker = DependencyChecker()
    checker.register("redis", check_redis_fn)
    status = checker.check("redis")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class DependencyStatus(str, Enum):
    AVAILABLE = "Available"
    SLOW = "Slow"
    UNAVAILABLE = "Unavailable"
    UNKNOWN = "Unknown"


@dataclass
class DependencyReport:
    """Aggregated dependency health report."""

    timestamp: float = field(default_factory=time.time)
    overall: DependencyStatus = DependencyStatus.UNKNOWN
    dependencies: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall.value,
            "dependencies": self.dependencies,
        }


class DependencyChecker:
    """Checks availability of infrastructure dependencies.

    Monitors: Redis, Kafka, Postgres, Broker Gateway, EventBus, etc.
    Each dependency has a ping/health check function.
    """

    def __init__(self, timeout_ms: float = 5000.0) -> None:
        self._checks: Dict[str, Callable[[], bool]] = {}
        self._timeout_ms = timeout_ms
        self._latency_history: Dict[str, List[float]] = {}
        self._failure_counts: Dict[str, int] = {}
        self._consecutive_failures: Dict[str, int] = {}

    def register(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a dependency check.

        check_fn should return True if the dependency is available.
        """
        self._checks[name] = check_fn
        self._latency_history.setdefault(name, [])
        self._failure_counts.setdefault(name, 0)
        self._consecutive_failures.setdefault(name, 0)

    def check(self, name: str) -> Dict[str, Any]:
        """Check a single dependency."""
        if name not in self._checks:
            return {
                "dependency": name,
                "status": DependencyStatus.UNKNOWN.value,
                "latency_ms": 0,
                "consecutive_failures": 0,
                "message": "Not registered",
            }

        start = time.time()
        try:
            available = self._checks[name]()
            latency = (time.time() - start) * 1000.0
        except Exception:
            available = False
            latency = (time.time() - start) * 1000.0

        self._latency_history[name].append(latency)
        if len(self._latency_history[name]) > 100:
            self._latency_history[name] = self._latency_history[name][-100:]

        if available:
            self._consecutive_failures[name] = 0
            if latency < 100.0:
                status = DependencyStatus.AVAILABLE
            elif latency < 500.0:
                status = DependencyStatus.SLOW
            else:
                status = DependencyStatus.SLOW
        else:
            self._consecutive_failures[name] += 1
            self._failure_counts[name] += 1
            status = DependencyStatus.UNAVAILABLE

        return {
            "dependency": name,
            "status": status.value,
            "latency_ms": round(latency, 2),
            "consecutive_failures": self._consecutive_failures[name],
            "total_failures": self._failure_counts[name],
            "avg_latency_ms": round(self._avg_latency(name), 2),
        }

    def check_all(self) -> DependencyReport:
        """Check all registered dependencies."""
        results: Dict[str, Dict[str, Any]] = {}
        any_unavailable = False
        any_slow = False

        for name in self._checks:
            r = self.check(name)
            results[name] = r
            if r["status"] == DependencyStatus.UNAVAILABLE.value:
                any_unavailable = True
            elif r["status"] == DependencyStatus.SLOW.value:
                any_slow = True

        if any_unavailable:
            overall = DependencyStatus.UNAVAILABLE
        elif any_slow:
            overall = DependencyStatus.SLOW
        else:
            overall = DependencyStatus.AVAILABLE

        return DependencyReport(
            overall=overall,
            dependencies=results,
        )

    def is_available(self, name: str) -> bool:
        """Quick check if a dependency is available."""
        result = self.check(name)
        return result["status"] != DependencyStatus.UNAVAILABLE.value

    def _avg_latency(self, name: str) -> float:
        history = self._latency_history.get(name, [])
        if not history:
            return 0.0
        return sum(history[-20:]) / min(len(history), 20)
