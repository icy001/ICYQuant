"""
ICYQuant Infrastructure - Health Checker

Multi-level health checking: system, module, service, and dependency health.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    response_time_ms: float = 0
    check_id: str = field(default_factory=lambda: __import__('uuid').uuid4().__str__())
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "responseTimeMs": self.response_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class HealthChecker:
    """
    Multi-level health checker for the platform.

    Supports system-level, module-level, service-level,
    and dependency-level health checks.
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self._history: List[Dict] = []
        self._max_history = 500

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], HealthCheckResult],
    ):
        self._checks[name] = check_fn
        logger.debug(f"Health check registered: {name}")

    def run_check(self, name: str) -> HealthCheckResult:
        check_fn = self._checks.get(name)
        if not check_fn:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Check not registered",
            )
        try:
            result = check_fn()
            self._results[name] = result
            return result
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
            self._results[name] = result
            return result

    def run_all_checks(self) -> List[HealthCheckResult]:
        results = []
        for name in self._checks:
            result = self.run_check(name)
            results.append(result)

        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "results": {r.name: r.status.value for r in results},
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return results

    def get_result(self, name: str) -> Optional[HealthCheckResult]:
        return self._results.get(name)

    def get_overall_status(self) -> HealthStatus:
        results = list(self._results.values())
        if not results:
            return HealthStatus.UNKNOWN

        statuses = [r.status for r in results]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.UNKNOWN

    def get_healthy_checks(self) -> List[HealthCheckResult]:
        return [r for r in self._results.values() if r.status == HealthStatus.HEALTHY]

    def get_unhealthy_checks(self) -> List[HealthCheckResult]:
        return [r for r in self._results.values() if r.status == HealthStatus.UNHEALTHY]

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "overallStatus": self.get_overall_status().value,
            "totalChecks": len(self._checks),
            "healthy": len(self.get_healthy_checks()),
            "unhealthy": len(self.get_unhealthy_checks()),
            "results": [r.to_dict() for r in self._results.values()],
        }

    def to_dict(self) -> Dict:
        return self.get_status()
