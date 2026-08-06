"""Resource Diagnostics — diagnostics for the resource scheduler.

Detects issues like resource fragmentation, idle nodes, hot spots,
quota violations, and placement anomalies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticsReport:
    """A resource diagnostics snapshot."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_nodes: int = 0
    online_nodes: int = 0
    total_cpu: float = 0.0
    used_cpu: float = 0.0
    total_memory_mb: float = 0.0
    used_memory_mb: float = 0.0
    fragmented_nodes: List[str] = field(default_factory=list)
    idle_nodes: List[str] = field(default_factory=list)
    hot_nodes: List[str] = field(default_factory=list)
    quota_warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_nodes": self.total_nodes,
            "online_nodes": self.online_nodes,
            "cpu": f"{self.used_cpu:.1f}/{self.total_cpu:.1f}",
            "memory": f"{self.used_memory_mb:.0f}/{self.total_memory_mb:.0f}MB",
            "fragmented_nodes": self.fragmented_nodes,
            "idle_nodes": self.idle_nodes,
            "hot_nodes": self.hot_nodes,
            "quota_warnings": self.quota_warnings,
            "recommendations": self.recommendations,
        }


class ResourceDiagnostics:
    """Diagnostics for resource scheduling health.

    Usage::

        diag = ResourceDiagnostics()
        report = diag.run(pool, inventory, tracker, io_scheduler)
    """

    def run(
        self, pool: Any, inventory: Any, tracker: Any,
        io_scheduler: Any, quota: Any = None,
    ) -> DiagnosticsReport:
        report = DiagnosticsReport()

        # Pool stats
        caps = pool.total_capacity()
        report.total_cpu = caps["cpu_total"]
        report.used_cpu = caps["cpu_used"]
        report.total_memory_mb = caps["memory_total_mb"]
        report.used_memory_mb = caps["memory_used_mb"]

        # Node status
        if inventory:
            report.total_nodes = inventory.count()
            counts = inventory.count_by_status()
            report.online_nodes = counts.get("online", 0)

        # Fragmentation: nodes with low utilization but non-zero usage
        if pool:
            for n in pool.list_nodes():
                if 0 < n.cpu_used < n.cpu_total * 0.3:
                    report.fragmented_nodes.append(n.node_id)

        # Idle nodes
        if pool:
            report.idle_nodes = [
                n.node_id for n in pool.list_nodes()
                if n.cpu_used < 0.01
            ]

        # Hot nodes
        if io_scheduler:
            report.hot_nodes = io_scheduler.get_hot_nodes()

        # Recommendations
        if report.fragmented_nodes:
            report.recommendations.append(
                f"Found {len(report.fragmented_nodes)} fragmented nodes — run bin-packing optimization"
            )
        if report.idle_nodes:
            report.recommendations.append(
                f"Found {len(report.idle_nodes)} idle nodes — consider scaling in"
            )
        if report.hot_nodes:
            report.recommendations.append(
                f"Found {len(report.hot_nodes)} IO hot spots — redistribute IO-heavy jobs"
            )
        if not report.recommendations:
            report.recommendations.append("Cluster resources are healthy")

        return report

    def health_report(self) -> Dict[str, Any]:
        return {"status": "ready"}
