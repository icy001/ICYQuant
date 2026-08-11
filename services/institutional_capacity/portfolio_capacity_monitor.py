"""
Portfolio Capacity Monitor — Watches portfolio-level capacity utilization.

Monitors aggregate utilization, asset overlaps, factor concentrations,
and triggers alerts when thresholds are breached.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .portfolio_capacity import PortfolioCapacity, PortfolioCapacityState, AssetOverlap, FactorOverlap


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CapacityAlert:
    """An alert triggered by portfolio capacity monitoring."""

    alert_id: str = field(default_factory=lambda: f"PA-{uuid.uuid4().hex[:8]}")
    severity: AlertSeverity = AlertSeverity.INFO
    category: str = ""
    message: str = ""
    metric: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "metric": self.metric,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
        }


class PortfolioCapacityMonitor:
    """Monitors portfolio capacity and triggers alerts on breaches."""

    def __init__(self):
        self._capacity: Optional[PortfolioCapacity] = None
        self._alerts: List[CapacityAlert] = []
        self._alert_handlers: List[Callable[[CapacityAlert], None]] = []

        # Thresholds (configurable)
        self.utilization_warning: float = 0.70
        self.utilization_critical: float = 0.85
        self.overlap_warning: float = 3  # max strategies per asset
        self.factor_utilization_warning: float = 0.70
        self.factor_utilization_critical: float = 0.90
        self.capacity_discount_warning: float = 0.85
        self.constrained_pct_warning: float = 0.30

    def update(self, capacity: PortfolioCapacity) -> List[CapacityAlert]:
        """Update monitored state and return any new alerts."""
        self._capacity = capacity
        new_alerts = self._evaluate_thresholds()
        self._alerts.extend(new_alerts)

        for alert in new_alerts:
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception:
                    pass

        return new_alerts

    def on_alert(self, handler: Callable[[CapacityAlert], None]) -> None:
        self._alert_handlers.append(handler)

    # ── Evaluation ───────────────────────────────────────────────

    def _evaluate_thresholds(self) -> List[CapacityAlert]:
        alerts: List[CapacityAlert] = []
        c = self._capacity
        if c is None:
            return alerts

        # Overall utilization
        if c.total_utilization >= self.utilization_critical:
            alerts.append(CapacityAlert(
                severity=AlertSeverity.CRITICAL,
                category="utilization",
                message=f"Portfolio utilization at {c.total_utilization:.1%} exceeds critical threshold",
                metric="total_utilization",
                current_value=c.total_utilization,
                threshold=self.utilization_critical,
            ))
        elif c.total_utilization >= self.utilization_warning:
            alerts.append(CapacityAlert(
                severity=AlertSeverity.WARNING,
                category="utilization",
                message=f"Portfolio utilization at {c.total_utilization:.1%} exceeds warning threshold",
                metric="total_utilization",
                current_value=c.total_utilization,
                threshold=self.utilization_warning,
            ))

        # Asset overlap
        oversubscribed = [o for o in c.asset_overlaps if o.is_oversubscribed]
        for overlap in oversubscribed:
            if overlap.overlap_ratio > 2.0:
                alerts.append(CapacityAlert(
                    severity=AlertSeverity.CRITICAL,
                    category="asset_overlap",
                    message=f"Asset {overlap.asset} oversubscribed {overlap.overlap_ratio:.1f}x "
                            f"({len(overlap.strategy_ids)} strategies)",
                    metric=f"overlap_{overlap.asset}",
                    current_value=overlap.overlap_ratio,
                    threshold=2.0,
                ))
            else:
                alerts.append(CapacityAlert(
                    severity=AlertSeverity.WARNING,
                    category="asset_overlap",
                    message=f"Asset {overlap.asset} oversubscribed {overlap.overlap_ratio:.1f}x",
                    metric=f"overlap_{overlap.asset}",
                    current_value=overlap.overlap_ratio,
                    threshold=1.0,
                ))

        # Factor breaches
        for factor in c.factor_overlaps:
            if factor.exposure_ratio >= self.factor_utilization_critical:
                alerts.append(CapacityAlert(
                    severity=AlertSeverity.CRITICAL,
                    category="factor_concentration",
                    message=f"Factor {factor.factor} exposure at {factor.exposure_ratio:.1%}",
                    metric=f"factor_{factor.factor}",
                    current_value=factor.exposure_ratio,
                    threshold=self.factor_utilization_critical,
                ))
            elif factor.exposure_ratio >= self.factor_utilization_warning:
                alerts.append(CapacityAlert(
                    severity=AlertSeverity.WARNING,
                    category="factor_concentration",
                    message=f"Factor {factor.factor} exposure at {factor.exposure_ratio:.1%}",
                    metric=f"factor_{factor.factor}",
                    current_value=factor.exposure_ratio,
                    threshold=self.factor_utilization_warning,
                ))

        # Capacity discount
        if c.capacity_discount < self.capacity_discount_warning:
            alerts.append(CapacityAlert(
                severity=AlertSeverity.WARNING,
                category="capacity_discount",
                message=f"Portfolio capacity discounted to {c.capacity_discount:.1%}",
                metric="capacity_discount",
                current_value=c.capacity_discount,
                threshold=self.capacity_discount_warning,
            ))

        # Constrained strategy ratio
        constrained_pct = c.constrained_count / max(c.strategy_count, 1)
        if constrained_pct >= self.constrained_pct_warning:
            alerts.append(CapacityAlert(
                severity=AlertSeverity.WARNING,
                category="constrained_strategies",
                message=f"{(constrained_pct * 100):.0f}% of strategies at/over capacity",
                metric="constrained_pct",
                current_value=constrained_pct,
                threshold=self.constrained_pct_warning,
            ))

        return alerts

    # ── Query ─────────────────────────────────────────────────────

    def recent_alerts(self, limit: int = 50) -> List[CapacityAlert]:
        return self._alerts[-limit:]

    def alerts_by_severity(self, severity: AlertSeverity) -> List[CapacityAlert]:
        return [a for a in self._alerts if a.severity == severity]

    def alerts_by_category(self, category: str) -> List[CapacityAlert]:
        return [a for a in self._alerts if a.category == category]

    def clear_alerts(self) -> None:
        self._alerts.clear()

    def status(self) -> Dict[str, Any]:
        if self._capacity is None:
            return {"status": "no_data"}
        return {
            "status": "monitoring",
            "state": self._capacity.state.value,
            "total_utilization": round(self._capacity.total_utilization * 100, 2),
            "constrained_strategies": self._capacity.constrained_count,
            "active_alerts": len([
                a for a in self._alerts
                if (datetime.now(timezone.utc) - a.timestamp).total_seconds() < 3600
            ]),
            "critical_alerts": len(self.alerts_by_severity(AlertSeverity.CRITICAL)),
            "warning_alerts": len(self.alerts_by_severity(AlertSeverity.WARNING)),
        }

    def summary(self) -> Dict[str, Any]:
        return self.status()
