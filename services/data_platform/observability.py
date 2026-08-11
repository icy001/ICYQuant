"""
ICYQuant Data Platform Observability — unified observability layer.

Provides end-to-end monitoring across all data platform subsystems:
Connectivity, Normalization, Streaming, Data Lake, API, and Audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ObservabilitySnapshot:
    """Snapshot of platform observability state."""
    connectivity: dict[str, Any] = field(default_factory=dict)
    normalization: dict[str, Any] = field(default_factory=dict)
    streaming: dict[str, Any] = field(default_factory=dict)
    data_lake: dict[str, Any] = field(default_factory=dict)
    api: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


class DataPlatformObservability:
    """Unified observability layer for the data platform.

    Monitors:
        - Connectivity: Exchange connections, throughput, latency
        - Normalization: Processing rates, error rates, schema violations
        - Streaming: Event throughput, lag, consumer health
        - Data Lake: Storage usage, query performance, partition health
        - API: Request rates, latency, error rates
        - Audit: Event counts, compliance status
    """

    def __init__(self) -> None:
        self._subsystems: dict[str, dict[str, Any]] = {
            "connectivity": {"status": "unknown", "throughput": 0, "errors": 0},
            "normalization": {"status": "unknown", "throughput": 0, "errors": 0},
            "streaming": {"status": "unknown", "throughput": 0, "lag_ms": 0},
            "data_lake": {"status": "unknown", "storage_bytes": 0, "queries": 0},
            "api": {"status": "unknown", "requests": 0, "errors": 0},
            "audit": {"status": "unknown", "events": 0},
        }

    def update_subsystem(self, name: str, metrics: dict[str, Any]) -> None:
        """Update metrics for a subsystem."""
        if name in self._subsystems:
            self._subsystems[name].update(metrics)

    def set_subsystem_healthy(self, name: str) -> None:
        if name in self._subsystems:
            self._subsystems[name]["status"] = "healthy"

    def set_subsystem_degraded(self, name: str) -> None:
        if name in self._subsystems:
            self._subsystems[name]["status"] = "degraded"

    def set_subsystem_unhealthy(self, name: str, reason: str = "") -> None:
        if name in self._subsystems:
            self._subsystems[name]["status"] = "unhealthy"
            self._subsystems[name]["reason"] = reason

    def get_snapshot(self) -> ObservabilitySnapshot:
        """Get a full observability snapshot."""
        return ObservabilitySnapshot(
            connectivity=self._subsystems.get("connectivity", {}),
            normalization=self._subsystems.get("normalization", {}),
            streaming=self._subsystems.get("streaming", {}),
            data_lake=self._subsystems.get("data_lake", {}),
            api=self._subsystems.get("api", {}),
            audit=self._subsystems.get("audit", {}),
        )

    def get_subsystem(self, name: str) -> Optional[dict[str, Any]]:
        return self._subsystems.get(name)

    def get_overall_status(self) -> str:
        """Determine overall platform status."""
        statuses = [s.get("status", "unknown") for s in self._subsystems.values()]
        if "unhealthy" in statuses:
            return "unhealthy"
        if "degraded" in statuses:
            return "degraded"
        if all(s == "healthy" for s in statuses):
            return "healthy"
        return "unknown"

    def get_summary(self) -> dict[str, Any]:
        return {
            "status": self.get_overall_status(),
            "subsystems": {
                name: {"status": s.get("status")}
                for name, s in self._subsystems.items()
            },
        }

    @property
    def subsystem_count(self) -> int:
        return len(self._subsystems)
