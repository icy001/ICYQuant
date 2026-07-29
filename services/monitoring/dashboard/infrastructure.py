"""Infrastructure Dashboard.

Infrastructure monitoring:
- Broker Gateway health
- API service status
- Redis, Kafka, Database status
- Circuit breaker states
- Failover status
- Resource utilization (CPU, Memory, Disk)

Usage::

    dashboard = InfrastructureDashboard(
        dependency_checker,
        circuit_breaker_registry,
        failover_manager,
    )
    snapshot = dashboard.generate()
    print(snapshot.to_dict())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.metrics.collector import MetricsCollector, SystemMetrics


@dataclass
class InfrastructureSnapshot:
    """Real-time infrastructure health snapshot."""

    # Resource utilization
    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    disk_pct: float = 0.0

    # Dependencies
    redis_status: str = "Unknown"
    redis_latency_ms: float = 0.0
    kafka_status: str = "Unknown"
    kafka_latency_ms: float = 0.0
    postgres_status: str = "Unknown"
    postgres_latency_ms: float = 0.0

    # API
    api_latency_p50: float = 0.0
    api_latency_p99: float = 0.0
    api_error_rate: float = 0.0

    # Circuit breakers
    circuit_breakers_open: int = 0
    circuit_breakers_half_open: int = 0
    circuit_breakers_closed: int = 0

    # Failover
    failover_active: int = 0
    failover_total: int = 0

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resources": {
                "cpu_pct": round(self.cpu_pct, 1),
                "memory_pct": round(self.memory_pct, 1),
                "disk_pct": round(self.disk_pct, 1),
            },
            "dependencies": {
                "redis": {
                    "status": self.redis_status,
                    "latency_ms": round(self.redis_latency_ms, 2),
                },
                "kafka": {
                    "status": self.kafka_status,
                    "latency_ms": round(self.kafka_latency_ms, 2),
                },
                "postgres": {
                    "status": self.postgres_status,
                    "latency_ms": round(self.postgres_latency_ms, 2),
                },
            },
            "api": {
                "latency_p50_ms": round(self.api_latency_p50, 2),
                "latency_p99_ms": round(self.api_latency_p99, 2),
                "error_rate": round(self.api_error_rate, 4),
            },
            "circuit_breakers": {
                "open": self.circuit_breakers_open,
                "half_open": self.circuit_breakers_half_open,
                "closed": self.circuit_breakers_closed,
            },
            "failover": {
                "active": self.failover_active,
                "total_targets": self.failover_total,
            },
            "timestamp": self.timestamp,
        }


class InfrastructureDashboard:
    """Generates infrastructure monitoring dashboard."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        dependency_checker: Any = None,
        circuit_breaker_registry: Any = None,
        failover_manager: Any = None,
    ) -> None:
        self._metrics = metrics_collector
        self._deps = dependency_checker
        self._cb_registry = circuit_breaker_registry
        self._failover = failover_manager

    def generate(self) -> InfrastructureSnapshot:
        """Generate infrastructure dashboard snapshot."""
        snapshot = InfrastructureSnapshot()

        # System metrics
        if self._metrics:
            sys = self._metrics.get_system()
            snapshot.cpu_pct = sys.cpu_pct
            snapshot.memory_pct = sys.memory_pct
            snapshot.disk_pct = sys.disk_pct
            snapshot.redis_status = "Available" if sys.redis_available else "Unavailable"
            snapshot.redis_latency_ms = sys.redis_latency_ms
            snapshot.kafka_status = "Available" if sys.kafka_available else "Unavailable"
            snapshot.kafka_latency_ms = sys.kafka_latency_ms
            snapshot.postgres_status = "Available" if sys.postgres_available else "Unavailable"
            snapshot.postgres_latency_ms = sys.postgres_latency_ms
            snapshot.api_latency_p50 = sys.api_latency_p50
            snapshot.api_latency_p99 = sys.api_latency_p99
            snapshot.api_error_rate = sys.api_error_rate

        # Circuit breakers
        if self._cb_registry:
            summary = self._cb_registry.status_summary()
            snapshot.circuit_breakers_open = summary.get("open", 0)
            snapshot.circuit_breakers_half_open = summary.get("half_open", 0)
            snapshot.circuit_breakers_closed = summary.get("closed", 0)

        # Failover
        if self._failover:
            status = self._failover.get_all_status()
            snapshot.failover_total = len(status)
            snapshot.failover_active = sum(
                1 for s in status.values()
                if s.get("status") == "failed_over"
            )

        return snapshot

    def generate_dict(self) -> Dict[str, Any]:
        """Generate infrastructure snapshot as dict."""
        return self.generate().to_dict()
