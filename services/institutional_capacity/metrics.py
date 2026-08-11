"""
Capacity Metrics — Prometheus-compatible metrics for institutional capacity.

Exposes 20+ gauges, counters, and histograms for monitoring:
strategy capacity, market liquidity, execution, impact, and portfolio-wide metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class MetricValue:
    """A single metric data point."""

    name: str = ""
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metric_type: str = "gauge"  # gauge, counter, histogram

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "type": self.metric_type,
            "timestamp": self.timestamp,
        }

    def prometheus_format(self) -> str:
        """Format as Prometheus text exposition format."""
        label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
        label_suffix = f"{{{label_str}}}" if label_str else ""
        return f"{self.name}{label_suffix} {self.value}"


class CapacityMetrics:
    """Central metrics registry for institutional capacity."""

    def __init__(self):
        self._metrics: Dict[str, MetricValue] = {}

    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None,
            metric_type: str = "gauge") -> None:
        self._metrics[name] = MetricValue(
            name=name, value=value, labels=labels or {}, metric_type=metric_type,
        )

    def get(self, name: str) -> Optional[MetricValue]:
        return self._metrics.get(name)

    def value(self, name: str, default: float = 0.0) -> float:
        m = self._metrics.get(name)
        return m.value if m else default

    def all_metrics(self) -> List[MetricValue]:
        return list(self._metrics.values())

    def to_prometheus(self) -> str:
        return "\n".join(m.prometheus_format() for m in self._metrics.values())

    def to_dict(self) -> Dict[str, Any]:
        return {name: m.to_dict() for name, m in self._metrics.items()}

    def summary(self) -> Dict[str, Any]:
        return {"metric_count": len(self._metrics), "metrics": self.to_dict()}


class CapacityMetricsCollector:
    """Collects and exposes all capacity-related metrics."""

    # ── Strategy Capacity Gauges ──────────────────────────────────

    STRATEGY_CAPACITY = "icyquant_strategy_capacity"
    STRATEGY_CAPACITY_UTILIZATION = "icyquant_strategy_capacity_utilization"
    STRATEGY_CAPACITY_REMAINING = "icyquant_strategy_capacity_remaining"
    STRATEGY_CAPACITY_OPTIMAL = "icyquant_strategy_capacity_optimal"
    STRATEGY_CAPACITY_ALPHA_DECAY = "icyquant_strategy_capacity_alpha_decay"
    STRATEGY_CAPACITY_STATE = "icyquant_strategy_capacity_state"

    STRATEGY_CAPACITY_TOTAL = "icyquant_strategy_capacity_total"

    # ── Market Liquidity Gauges ───────────────────────────────────

    LIQUIDITY_SCORE = "icyquant_liquidity_score"
    LIQUIDITY_REGIME = "icyquant_liquidity_regime"
    LIQUIDITY_SPREAD_BPS = "icyquant_liquidity_spread_bps"
    LIQUIDITY_VOLUME = "icyquant_liquidity_volume"
    LIQUIDITY_DEPTH = "icyquant_liquidity_depth"

    # ── Participation & Execution Gauges ──────────────────────────

    PARTICIPATION_RATE = "icyquant_participation_rate"
    PARTICIPATION_LIMIT = "icyquant_participation_limit"
    EXECUTION_WINDOW_SECONDS = "icyquant_execution_window_seconds"
    EXECUTION_THROTTLE = "icyquant_execution_throttle"
    EXECUTION_ORDERS_ACTIVE = "icyquant_execution_orders_active"

    # ── Market Impact Gauges ──────────────────────────────────────

    IMPACT_ESTIMATED_BPS = "icyquant_impact_estimated_bps"
    IMPACT_REALIZED_BPS = "icyquant_impact_realized_bps"
    IMPACT_BUDGET_LIMIT = "icyquant_impact_budget_limit"
    IMPACT_BUDGET_CONSUMED = "icyquant_impact_budget_consumed"
    IMPACT_BUDGET_REMAINING = "icyquant_impact_budget_remaining"

    # ── Portfolio Capacity Gauges ─────────────────────────────────

    PORTFOLIO_CAPACITY_TOTAL = "icyquant_portfolio_capacity_total"
    PORTFOLIO_CAPACITY_UTILIZATION = "icyquant_portfolio_capacity_utilization"
    PORTFOLIO_CAPACITY_EFFECTIVE = "icyquant_portfolio_capacity_effective"
    PORTFOLIO_CAPACITY_HEADROOM = "icyquant_portfolio_capacity_headroom"
    PORTFOLIO_CAPACITY_CONSTRAINED_COUNT = "icyquant_portfolio_capacity_constrained_count"
    PORTFOLIO_CAPACITY_DISCOUNT = "icyquant_portfolio_capacity_discount"

    # ── Capacity Decision Counters ────────────────────────────────

    DECISIONS_TOTAL = "icyquant_capacity_decisions_total"
    DECISIONS_APPROVED = "icyquant_capacity_decisions_approved"
    DECISIONS_RESIZED = "icyquant_capacity_decisions_resized"
    DECISIONS_SPLIT = "icyquant_capacity_decisions_split"
    DECISIONS_DEFERRED = "icyquant_capacity_decisions_deferred"
    DECISIONS_REJECTED = "icyquant_capacity_decisions_rejected"

    # ── Guard Counters ────────────────────────────────────────────

    GUARD_TOTAL = "icyquant_capacity_guard_total"
    GUARD_ALLOWED = "icyquant_capacity_guard_allowed"
    GUARD_RESIZED = "icyquant_capacity_guard_resized"
    GUARD_DEFERRED = "icyquant_capacity_guard_deferred"
    GUARD_REJECTED = "icyquant_capacity_guard_rejected"

    # ── Stress & Scenario Counters ────────────────────────────────

    STRESS_SCENARIOS_RUN = "icyquant_capacity_stress_scenarios_run"
    STRESS_FATAL_COUNT = "icyquant_capacity_stress_fatal_count"
    STRESS_SURVIVABLE_COUNT = "icyquant_capacity_stress_survivable_count"

    # ── Regime Counters ───────────────────────────────────────────

    REGIME_SHIFTS_TOTAL = "icyquant_capacity_regime_shifts_total"
    REGIME_CRISIS_ACTIVE = "icyquant_capacity_regime_crisis_active"

    # ── Health Gauges ─────────────────────────────────────────────

    COMPONENT_HEALTH = "icyquant_capacity_component_health"
    UPTIME_SECONDS = "icyquant_capacity_uptime_seconds"

    def __init__(self):
        self._metrics = CapacityMetrics()

    def collect(self) -> CapacityMetrics:
        return self._metrics

    # ── Convenience Setters ───────────────────────────────────────

    def set_strategy_capacity(self, strategy_id: str, current: float, max_cap: float,
                               utilization: float, remaining: float, optimal: float,
                               alpha_decay: float = 0.0, state: str = "unknown") -> None:
        labels = {"strategy_id": strategy_id}
        self._metrics.set(self.STRATEGY_CAPACITY, max_cap, labels)
        self._metrics.set(self.STRATEGY_CAPACITY_UTILIZATION, utilization, labels)
        self._metrics.set(self.STRATEGY_CAPACITY_REMAINING, remaining, labels)
        self._metrics.set(self.STRATEGY_CAPACITY_OPTIMAL, optimal, labels)
        self._metrics.set(self.STRATEGY_CAPACITY_ALPHA_DECAY, alpha_decay, labels)
        self._metrics.set(self.STRATEGY_CAPACITY_TOTAL, current, labels)

    def set_liquidity(self, asset: str, score: float, regime: str,
                       spread_bps: float, volume: float, depth: float) -> None:
        labels = {"asset": asset}
        self._metrics.set(self.LIQUIDITY_SCORE, score, labels)
        self._metrics.set(self.LIQUIDITY_SPREAD_BPS, spread_bps, labels)
        self._metrics.set(self.LIQUIDITY_VOLUME, volume, labels)
        self._metrics.set(self.LIQUIDITY_DEPTH, depth, labels)

    def set_participation(self, strategy_id: str, rate: float, limit: float) -> None:
        labels = {"strategy_id": strategy_id}
        self._metrics.set(self.PARTICIPATION_RATE, rate, labels)
        self._metrics.set(self.PARTICIPATION_LIMIT, limit, labels)

    def set_execution(self, strategy_id: str, window_seconds: float,
                       throttle_rate: float, active_orders: int) -> None:
        labels = {"strategy_id": strategy_id}
        self._metrics.set(self.EXECUTION_WINDOW_SECONDS, window_seconds, labels)
        self._metrics.set(self.EXECUTION_THROTTLE, throttle_rate, labels)
        self._metrics.set(self.EXECUTION_ORDERS_ACTIVE, float(active_orders), labels)

    def set_impact(self, asset: str, estimated_bps: float, realized_bps: float,
                    budget_limit: float, budget_consumed: float) -> None:
        labels = {"asset": asset}
        self._metrics.set(self.IMPACT_ESTIMATED_BPS, estimated_bps, labels)
        self._metrics.set(self.IMPACT_REALIZED_BPS, realized_bps, labels)
        self._metrics.set(self.IMPACT_BUDGET_LIMIT, budget_limit, labels)
        self._metrics.set(self.IMPACT_BUDGET_CONSUMED, budget_consumed, labels)
        self._metrics.set(
            self.IMPACT_BUDGET_REMAINING,
            max(0, budget_limit - budget_consumed),
            labels,
        )

    def set_portfolio(self, total: float, utilization: float,
                       effective: float, headroom: float,
                       constrained_count: int, discount: float) -> None:
        self._metrics.set(self.PORTFOLIO_CAPACITY_TOTAL, total)
        self._metrics.set(self.PORTFOLIO_CAPACITY_UTILIZATION, utilization)
        self._metrics.set(self.PORTFOLIO_CAPACITY_EFFECTIVE, effective)
        self._metrics.set(self.PORTFOLIO_CAPACITY_HEADROOM, headroom)
        self._metrics.set(self.PORTFOLIO_CAPACITY_CONSTRAINED_COUNT, float(constrained_count))
        self._metrics.set(self.PORTFOLIO_CAPACITY_DISCOUNT, discount)

    def inc_decisions(self, total: int = 0, approved: int = 0,
                       resized: int = 0, split: int = 0,
                       deferred: int = 0, rejected: int = 0) -> None:
        self._metrics.set(self.DECISIONS_TOTAL, float(total + self._metrics.value(self.DECISIONS_TOTAL)), metric_type="counter")
        self._metrics.set(self.DECISIONS_APPROVED, float(approved + self._metrics.value(self.DECISIONS_APPROVED)), metric_type="counter")
        self._metrics.set(self.DECISIONS_RESIZED, float(resized + self._metrics.value(self.DECISIONS_RESIZED)), metric_type="counter")
        self._metrics.set(self.DECISIONS_SPLIT, float(split + self._metrics.value(self.DECISIONS_SPLIT)), metric_type="counter")
        self._metrics.set(self.DECISIONS_DEFERRED, float(deferred + self._metrics.value(self.DECISIONS_DEFERRED)), metric_type="counter")
        self._metrics.set(self.DECISIONS_REJECTED, float(rejected + self._metrics.value(self.DECISIONS_REJECTED)), metric_type="counter")

    def inc_guard(self, total: int = 0, allowed: int = 0,
                   resized: int = 0, deferred: int = 0, rejected: int = 0) -> None:
        self._metrics.set(self.GUARD_TOTAL, float(total + self._metrics.value(self.GUARD_TOTAL)), metric_type="counter")
        self._metrics.set(self.GUARD_ALLOWED, float(allowed + self._metrics.value(self.GUARD_ALLOWED)), metric_type="counter")
        self._metrics.set(self.GUARD_RESIZED, float(resized + self._metrics.value(self.GUARD_RESIZED)), metric_type="counter")
        self._metrics.set(self.GUARD_DEFERRED, float(deferred + self._metrics.value(self.GUARD_DEFERRED)), metric_type="counter")
        self._metrics.set(self.GUARD_REJECTED, float(rejected + self._metrics.value(self.GUARD_REJECTED)), metric_type="counter")

    def set_health(self, component: str, healthy: bool, uptime: float) -> None:
        self._metrics.set(self.COMPONENT_HEALTH, 1.0 if healthy else 0.0, {"component": component})
        self._metrics.set(self.UPTIME_SECONDS, uptime, {"component": component})

    def set_stress_results(self, total: int, fatal: int, survivable: int) -> None:
        self._metrics.set(self.STRESS_SCENARIOS_RUN, float(total), metric_type="counter")
        self._metrics.set(self.STRESS_FATAL_COUNT, float(fatal))
        self._metrics.set(self.STRESS_SURVIVABLE_COUNT, float(survivable))

    def set_regime(self, shifts: int, crisis_active: bool) -> None:
        self._metrics.set(self.REGIME_SHIFTS_TOTAL, float(shifts), metric_type="counter")
        self._metrics.set(self.REGIME_CRISIS_ACTIVE, 1.0 if crisis_active else 0.0)

    def export_prometheus(self) -> str:
        return self._metrics.to_prometheus()

    def summary(self) -> Dict[str, Any]:
        return {
            "metric_count": len(self._metrics.all_metrics()),
            "prometheus": self.export_prometheus(),
        }
