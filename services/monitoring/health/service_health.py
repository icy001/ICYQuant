"""Service Health Monitor.

Provides real-time health checking for all ICYQuant services:
- API, OMS, Risk, Portfolio, Ledger, EventBus, Broker, Execution
- Liveness / Readiness / Dependency checks
- Uptime tracking and SLA computation

Usage::

    monitor = ServiceHealthMonitor()
    monitor.register("OMS", check_fn=check_oms)
    report = monitor.check_all()
    print(report.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ServiceStatus(str, Enum):
    """Health status for a single service."""

    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"
    UNKNOWN = "Unknown"


@dataclass
class HealthReport:
    """Aggregated health report for all registered services."""

    timestamp: float = field(default_factory=time.time)
    overall_status: ServiceStatus = ServiceStatus.UNKNOWN
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        healthy = sum(
            1 for s in self.services.values()
            if s.get("status") == ServiceStatus.HEALTHY.value
        )
        total = len(self.services)
        return {
            "overall": self.overall_status.value,
            "healthy_count": healthy,
            "total_count": total,
            "ratio": f"{healthy}/{total}" if total > 0 else "0/0",
            "timestamp": self.timestamp,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp,
            "services": self.services,
            "details": self.details,
        }


class ServiceHealthMonitor:
    """Monitors health of all platform services.

    Each registered service has a check function that returns
    (status, latency_ms, message).
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[[], tuple[ServiceStatus, float, str]]] = {}
        self._start_times: Dict[str, float] = {}
        self._history: Dict[str, List[tuple[float, ServiceStatus]]] = {}

    def register(
        self,
        service_name: str,
        check_fn: Callable[[], tuple[ServiceStatus, float, str]],
    ) -> None:
        """Register a health check for a service."""
        self._checks[service_name] = check_fn
        self._start_times[service_name] = time.time()
        self._history.setdefault(service_name, [])

    def check(self, service_name: str) -> Dict[str, Any]:
        """Check a single service."""
        if service_name not in self._checks:
            return {
                "service": service_name,
                "status": ServiceStatus.UNKNOWN.value,
                "latency_ms": 0,
                "message": "Service not registered",
                "uptime_pct": 0.0,
            }

        check_fn = self._checks[service_name]
        try:
            status, latency, message = check_fn()
        except Exception as e:
            status = ServiceStatus.UNHEALTHY
            latency = 0.0
            message = f"Check raised exception: {e}"

        self._history[service_name].append((time.time(), status))
        # Trim history to last 1000 entries
        if len(self._history[service_name]) > 1000:
            self._history[service_name] = self._history[service_name][-1000:]

        uptime = self._compute_uptime(service_name)

        return {
            "service": service_name,
            "status": status.value,
            "latency_ms": round(latency, 2),
            "message": message,
            "uptime_pct": round(uptime, 4),
            "uptime_str": f"{uptime:.2f}%",
        }

    def check_all(self) -> HealthReport:
        """Check all registered services and produce a report."""
        results: Dict[str, Dict[str, Any]] = {}
        all_healthy = True
        any_degraded = False
        details: List[str] = []

        for name in self._checks:
            r = self.check(name)
            results[name] = r
            if r["status"] == ServiceStatus.UNHEALTHY.value:
                all_healthy = False
                details.append(f"[{name}] {r['message']}")
            elif r["status"] == ServiceStatus.DEGRADED.value:
                any_degraded = True
                details.append(f"[{name}] DEGRADED: {r['message']}")

        if all_healthy and not any_degraded:
            overall = ServiceStatus.HEALTHY
        elif not all_healthy:
            overall = ServiceStatus.UNHEALTHY
        else:
            overall = ServiceStatus.DEGRADED

        return HealthReport(
            overall_status=overall,
            services=results,
            details=details,
        )

    def get_uptime(self, service_name: str) -> float:
        """Get uptime percentage for a service."""
        return self._compute_uptime(service_name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_uptime(self, service_name: str) -> float:
        history = self._history.get(service_name, [])
        if not history:
            return 100.0
        healthy_count = sum(
            1 for _, s in history
            if s in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED)
        )
        return (healthy_count / len(history)) * 100.0
