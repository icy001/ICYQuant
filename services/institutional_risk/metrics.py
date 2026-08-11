"""RiskMetrics — Prometheus-style metrics for the risk subsystem.

Exposes all key risk metrics: VaR, ES, drawdown, survival,
factor risk, correlation risk, tail risk, stress results,
risk budget, and action counters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RiskMetricsSnapshot:
    """Complete risk metrics snapshot."""

    # VaR & ES
    capital_var_95: float = 0.0
    capital_var_99: float = 0.0
    capital_expected_shortfall: float = 0.0
    portfolio_var: Dict[str, float] = field(default_factory=dict)
    portfolio_es: Dict[str, float] = field(default_factory=dict)

    # Drawdown
    capital_drawdown_pct: float = 0.0
    strategy_drawdown_pct: Dict[str, float] = field(default_factory=dict)
    portfolio_drawdown_pct: Dict[str, float] = field(default_factory=dict)
    max_drawdown_pct: float = 0.0
    drawdown_recovery_ratio: float = 0.0

    # Factor
    factor_risk_contribution: Dict[str, float] = field(default_factory=dict)
    factor_concentration: Dict[str, float] = field(default_factory=dict)

    # Correlation
    correlation_risk: float = 0.0
    correlation_spike: float = 0.0
    average_pairwise_correlation: float = 0.0

    # Tail
    tail_risk_score: float = 0.0
    tail_dependence: float = 0.0

    # Stress
    stress_loss_pct: Dict[str, float] = field(default_factory=dict)
    stress_drawdown_pct: Dict[str, float] = field(default_factory=dict)
    stress_survival_score: Dict[str, float] = field(default_factory=dict)

    # Survival
    capital_survival_score: float = 100.0
    capital_survival_horizon_days: float = 0.0
    capital_erosion_rate: float = 0.0
    recovery_capacity: float = 1.0

    # Risk Budget
    risk_budget_total: float = 0.0
    risk_budget_used: float = 0.0
    risk_budget_available: float = 0.0
    risk_budget_utilization_pct: float = 0.0

    # Counters
    risk_budget_breaches_total: int = 0
    deleveraging_events_total: int = 0
    risk_freeze_events_total: int = 0
    emergency_liquidation_events_total: int = 0
    stress_tests_run_total: int = 0
    stress_tests_failed_total: int = 0
    survival_guard_rejections_total: int = 0


class RiskMetricsCollector:
    """Collects and exposes risk metrics.

    Can be integrated with Prometheus or custom monitoring.

    Usage::

        collector = RiskMetricsCollector()
        collector.update_var(95, 7_200_000)
        collector.update_survival(78.5)
        snapshot = collector.snapshot()
    """

    def __init__(self):
        self._metrics = RiskMetricsSnapshot()
        self._counter_callbacks: Dict[str, List[Callable[[], int]]] = {}

    # ── update methods ──────────────────────────────────────────────

    def update_var(
        self,
        confidence: float,
        value: float,
        level: str = "capital",
    ) -> None:
        if level == "capital":
            if abs(confidence - 0.95) < 0.01:
                self._metrics.capital_var_95 = value
            elif abs(confidence - 0.99) < 0.01:
                self._metrics.capital_var_99 = value

    def update_expected_shortfall(self, value: float) -> None:
        self._metrics.capital_expected_shortfall = value

    def update_drawdown(
        self,
        entity_id: str,
        drawdown_pct: float,
        level: str = "capital",
    ) -> None:
        if level == "capital":
            self._metrics.capital_drawdown_pct = drawdown_pct
        elif level == "strategy":
            self._metrics.strategy_drawdown_pct[entity_id] = drawdown_pct
        elif level == "portfolio":
            self._metrics.portfolio_drawdown_pct[entity_id] = drawdown_pct

        self._metrics.max_drawdown_pct = max(
            self._metrics.max_drawdown_pct, drawdown_pct
        )

    def update_survival(self, score: float) -> None:
        self._metrics.capital_survival_score = score

    def update_risk_budget(
        self,
        total: float,
        used: float,
    ) -> None:
        self._metrics.risk_budget_total = total
        self._metrics.risk_budget_used = used
        self._metrics.risk_budget_available = max(0.0, total - used)
        self._metrics.risk_budget_utilization_pct = (
            (used / max(total, 1e-9)) * 100 if total > 0 else 0.0
        )

    def update_factor(self, factor_name: str, risk: float) -> None:
        self._metrics.factor_risk_contribution[factor_name] = risk

    def update_correlation(self, avg_corr: float, spike: float = 0.0) -> None:
        self._metrics.average_pairwise_correlation = avg_corr
        self._metrics.correlation_risk = avg_corr
        self._metrics.correlation_spike = spike

    def update_tail_risk(self, score: float) -> None:
        self._metrics.tail_risk_score = score

    def update_stress(
        self,
        scenario_name: str,
        loss_pct: float,
        survival: float,
    ) -> None:
        self._metrics.stress_loss_pct[scenario_name] = loss_pct
        self._metrics.stress_survival_score[scenario_name] = survival
        self._metrics.stress_tests_run_total += 1

    def increment_breach(self) -> None:
        self._metrics.risk_budget_breaches_total += 1

    def increment_deleveraging(self) -> None:
        self._metrics.deleveraging_events_total += 1

    def increment_freeze(self) -> None:
        self._metrics.risk_freeze_events_total += 1

    def increment_emergency(self) -> None:
        self._metrics.emergency_liquidation_events_total += 1

    def increment_stress_failed(self) -> None:
        self._metrics.stress_tests_failed_total += 1

    def increment_survival_rejection(self) -> None:
        self._metrics.survival_guard_rejections_total += 1

    # ── snapshot ────────────────────────────────────────────────────

    def snapshot(self) -> RiskMetricsSnapshot:
        """Get current metrics snapshot."""
        return self._metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary for export."""
        m = self._metrics
        return {
            "icyquant_capital_var_95": m.capital_var_95,
            "icyquant_capital_var_99": m.capital_var_99,
            "icyquant_capital_expected_shortfall": m.capital_expected_shortfall,
            "icyquant_capital_drawdown": m.capital_drawdown_pct,
            "icyquant_capital_survival_score": m.capital_survival_score,
            "icyquant_capital_survival_horizon": m.capital_survival_horizon_days,
            "icyquant_capital_erosion_rate": m.capital_erosion_rate,
            "icyquant_recovery_capacity": m.recovery_capacity,
            "icyquant_risk_budget_total": m.risk_budget_total,
            "icyquant_risk_budget_used": m.risk_budget_used,
            "icyquant_risk_budget_available": m.risk_budget_available,
            "icyquant_risk_budget_breaches_total": m.risk_budget_breaches_total,
            "icyquant_deleveraging_events_total": m.deleveraging_events_total,
            "icyquant_risk_freeze_events_total": m.risk_freeze_events_total,
            "icyquant_emergency_liquidation_events_total": m.emergency_liquidation_events_total,
            "icyquant_correlation_risk": m.correlation_risk,
            "icyquant_correlation_spike": m.correlation_spike,
            "icyquant_tail_risk": m.tail_risk_score,
            "icyquant_tail_dependence": m.tail_dependence,
            "icyquant_stress_tests_run": m.stress_tests_run_total,
            "icyquant_stress_tests_failed": m.stress_tests_failed_total,
        }

    def reset_counters(self) -> None:
        """Reset counter metrics (not gauges)."""
        m = self._metrics
        m.risk_budget_breaches_total = 0
        m.deleveraging_events_total = 0
        m.risk_freeze_events_total = 0
        m.emergency_liquidation_events_total = 0
        m.stress_tests_run_total = 0
        m.stress_tests_failed_total = 0
        m.survival_guard_rejections_total = 0
