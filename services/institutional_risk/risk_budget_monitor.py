"""RiskBudgetMonitor — real-time risk budget consumption monitoring.

Monitors risk budget usage, detects approach to limits,
and triggers warnings before breaches occur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BudgetAlert:
    """A risk budget alert."""

    entity_id: str
    alert_type: str  # WARNING, BREACH, EXHAUSTED
    utilization_pct: float
    budget: float
    used: float
    message: str
    timestamp: float = 0.0


@dataclass
class MonitorStatus:
    """Risk budget monitor status."""

    total_budget: float = 0.0
    total_used: float = 0.0
    utilization_pct: float = 0.0
    alerts: List[BudgetAlert] = field(default_factory=list)
    active_warnings: int = 0
    active_breaches: int = 0


class RiskBudgetMonitor:
    """Real-time risk budget monitoring.

    Usage::

        monitor = RiskBudgetMonitor(total_budget=8_000_000)
        alerts = monitor.update({"strat_A": 3_500_000, "strat_B": 4_200_000})
    """

    def __init__(
        self,
        total_budget: float,
        warning_threshold_pct: float = 80.0,
        breach_threshold_pct: float = 95.0,
        exhaustion_threshold_pct: float = 100.0,
    ):
        self._total_budget = total_budget
        self._warning = warning_threshold_pct
        self._breach = breach_threshold_pct
        self._exhaustion = exhaustion_threshold_pct
        self._alerts: List[BudgetAlert] = []

    @property
    def total_budget(self) -> float:
        return self._total_budget

    def update(
        self,
        entity_usage: Dict[str, float],
        timestamp: Optional[float] = None,
    ) -> List[BudgetAlert]:
        """Update usage and generate alerts.

        Args:
            entity_usage: {entity_id: risk_used}
            timestamp: optional timestamp
        """
        import time
        ts = timestamp or time.time()

        total_used = sum(entity_usage.values())
        utilization = (total_used / max(self._total_budget, 1e-9)) * 100

        new_alerts: List[BudgetAlert] = []

        # total budget alerts
        if utilization >= self._exhaustion:
            new_alerts.append(BudgetAlert(
                entity_id="TOTAL",
                alert_type="EXHAUSTED",
                utilization_pct=utilization,
                budget=self._total_budget,
                used=total_used,
                message=f"Risk budget EXHAUSTED ({utilization:.0f}%)",
                timestamp=ts,
            ))
        elif utilization >= self._breach:
            new_alerts.append(BudgetAlert(
                entity_id="TOTAL",
                alert_type="BREACH",
                utilization_pct=utilization,
                budget=self._total_budget,
                used=total_used,
                message=f"Risk budget BREACH ({utilization:.0f}%)",
                timestamp=ts,
            ))
        elif utilization >= self._warning:
            new_alerts.append(BudgetAlert(
                entity_id="TOTAL",
                alert_type="WARNING",
                utilization_pct=utilization,
                budget=self._total_budget,
                used=total_used,
                message=f"Risk budget WARNING ({utilization:.0f}%)",
                timestamp=ts,
            ))

        self._alerts.extend(new_alerts)
        # keep last 1000
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

        return new_alerts

    def get_status(self) -> MonitorStatus:
        """Get current monitor status."""
        status = MonitorStatus(
            total_budget=self._total_budget,
            total_used=0.0,
            alerts=list(self._alerts[-20:]),
        )

        active = [a for a in self._alerts[-20:] if a.alert_type != "OK"]
        status.active_warnings = sum(1 for a in active if a.alert_type == "WARNING")
        status.active_breaches = sum(1 for a in active if a.alert_type in ("BREACH", "EXHAUSTED"))

        if self._alerts:
            last = self._alerts[-1]
            status.total_used = last.used
            status.utilization_pct = last.utilization_pct

        return status

    def reset(self) -> None:
        """Reset alerts."""
        self._alerts.clear()
