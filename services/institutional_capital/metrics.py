"""
Institutional Capital Metrics — Prometheus-compatible metrics for capital intelligence.

Metrics:
    icyquant_capital_pool_total, icyquant_capital_available, icyquant_capital_reserved,
    icyquant_capital_allocated, icyquant_capital_deployed, icyquant_capital_utilization,
    icyquant_strategy_capital, icyquant_strategy_capacity, icyquant_strategy_capacity_utilization,
    icyquant_capital_efficiency, icyquant_risk_adjusted_capital_efficiency,
    icyquant_marginal_capital_efficiency, icyquant_strategy_correlation,
    icyquant_factor_overlap, icyquant_risk_overlap, icyquant_liquidity_overlap,
    icyquant_capital_allocation_changes_total, icyquant_capital_reallocation_total,
    icyquant_capital_guard_rejections_total, icyquant_capital_stress_events_total
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CapitalMetrics:
    """Aggregated capital pool metrics snapshot."""

    # Capital Pool
    capital_pool_total: float = 0.0
    capital_available: float = 0.0
    capital_reserved: float = 0.0
    capital_allocated: float = 0.0
    capital_deployed: float = 0.0
    capital_utilization: float = 0.0       # allocated / total

    # Strategy-level
    strategy_capital: Dict[str, float] = field(default_factory=dict)
    strategy_capacity: Dict[str, float] = field(default_factory=dict)
    strategy_capacity_utilization: Dict[str, float] = field(default_factory=dict)

    # Efficiency
    capital_efficiency: float = 0.0
    risk_adjusted_capital_efficiency: float = 0.0
    marginal_capital_efficiency: float = 0.0

    # Overlap
    strategy_correlation: Dict[str, float] = field(default_factory=dict)
    factor_overlap: Dict[str, float] = field(default_factory=dict)
    risk_overlap: Dict[str, float] = field(default_factory=dict)
    liquidity_overlap: Dict[str, float] = field(default_factory=dict)

    # Counters
    capital_allocation_changes_total: int = 0
    capital_reallocation_total: int = 0
    capital_guard_rejections_total: int = 0
    capital_stress_events_total: int = 0

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = [
            f"# HELP icyquant_capital_pool_total Total capital in pool",
            f"# TYPE icyquant_capital_pool_total gauge",
            f"icyquant_capital_pool_total {self.capital_pool_total}",
            f"# HELP icyquant_capital_available Available capital",
            f"# TYPE icyquant_capital_available gauge",
            f"icyquant_capital_available {self.capital_available}",
            f"# HELP icyquant_capital_reserved Reserved capital",
            f"# TYPE icyquant_capital_reserved gauge",
            f"icyquant_capital_reserved {self.capital_reserved}",
            f"# HELP icyquant_capital_allocated Allocated capital",
            f"# TYPE icyquant_capital_allocated gauge",
            f"icyquant_capital_allocated {self.capital_allocated}",
            f"# HELP icyquant_capital_deployed Deployed capital",
            f"# TYPE icyquant_capital_deployed gauge",
            f"icyquant_capital_deployed {self.capital_deployed}",
            f"# HELP icyquant_capital_utilization Capital utilization ratio",
            f"# TYPE icyquant_capital_utilization gauge",
            f"icyquant_capital_utilization {self.capital_utilization}",
            f"# HELP icyquant_capital_efficiency Capital efficiency",
            f"# TYPE icyquant_capital_efficiency gauge",
            f"icyquant_capital_efficiency {self.capital_efficiency}",
            f"# HELP icyquant_risk_adjusted_capital_efficiency Risk-adjusted capital efficiency",
            f"# TYPE icyquant_risk_adjusted_capital_efficiency gauge",
            f"icyquant_risk_adjusted_capital_efficiency {self.risk_adjusted_capital_efficiency}",
            f"# HELP icyquant_marginal_capital_efficiency Marginal capital efficiency",
            f"# TYPE icyquant_marginal_capital_efficiency gauge",
            f"icyquant_marginal_capital_efficiency {self.marginal_capital_efficiency}",
            f"# HELP icyquant_capital_allocation_changes_total Total allocation changes",
            f"# TYPE icyquant_capital_allocation_changes_total counter",
            f"icyquant_capital_allocation_changes_total {self.capital_allocation_changes_total}",
            f"# HELP icyquant_capital_reallocation_total Total reallocations",
            f"# TYPE icyquant_capital_reallocation_total counter",
            f"icyquant_capital_reallocation_total {self.capital_reallocation_total}",
            f"# HELP icyquant_capital_guard_rejections_total Guard rejections",
            f"# TYPE icyquant_capital_guard_rejections_total counter",
            f"icyquant_capital_guard_rejections_total {self.capital_guard_rejections_total}",
            f"# HELP icyquant_capital_stress_events_total Stress events",
            f"# TYPE icyquant_capital_stress_events_total counter",
            f"icyquant_capital_stress_events_total {self.capital_stress_events_total}",
        ]

        # Per-strategy metrics
        for sid, cap in self.strategy_capital.items():
            lines.append(
                f'icyquant_strategy_capital{{strategy_id="{sid}"}} {cap}'
            )
        for sid, cap in self.strategy_capacity.items():
            lines.append(
                f'icyquant_strategy_capacity{{strategy_id="{sid}"}} {cap}'
            )
        for sid, util in self.strategy_capacity_utilization.items():
            lines.append(
                f'icyquant_strategy_capacity_utilization{{strategy_id="{sid}"}} {util}'
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capital_pool_total": self.capital_pool_total,
            "capital_available": self.capital_available,
            "capital_reserved": self.capital_reserved,
            "capital_allocated": self.capital_allocated,
            "capital_deployed": self.capital_deployed,
            "capital_utilization": self.capital_utilization,
            "capital_efficiency": self.capital_efficiency,
            "risk_adjusted_capital_efficiency": self.risk_adjusted_capital_efficiency,
            "marginal_capital_efficiency": self.marginal_capital_efficiency,
            "strategy_capital": self.strategy_capital,
            "strategy_capacity": self.strategy_capacity,
            "allocation_changes_total": self.capital_allocation_changes_total,
            "reallocation_total": self.capital_reallocation_total,
            "guard_rejections_total": self.capital_guard_rejections_total,
            "stress_events_total": self.capital_stress_events_total,
        }


class CapitalMetricsCollector:
    """Collects and aggregates capital intelligence metrics."""

    def __init__(self):
        self._allocation_changes = 0
        self._reallocations = 0
        self._guard_rejections = 0
        self._stress_events = 0

    def record_allocation_change(self) -> None:
        self._allocation_changes += 1

    def record_reallocation(self) -> None:
        self._reallocations += 1

    def record_guard_rejection(self) -> None:
        self._guard_rejections += 1

    def record_stress_event(self) -> None:
        self._stress_events += 1

    def collect(
        self,
        total_capital: float = 0.0,
        available: float = 0.0,
        reserved: float = 0.0,
        allocated: float = 0.0,
        deployed: float = 0.0,
        efficiency: float = 0.0,
        risk_adj_efficiency: float = 0.0,
        marginal_efficiency: float = 0.0,
        strategy_capitals: Optional[Dict[str, float]] = None,
        strategy_capacities: Optional[Dict[str, float]] = None,
        strategy_utils: Optional[Dict[str, float]] = None,
    ) -> CapitalMetrics:
        utilization = allocated / max(total_capital, 1.0)
        return CapitalMetrics(
            capital_pool_total=total_capital,
            capital_available=available,
            capital_reserved=reserved,
            capital_allocated=allocated,
            capital_deployed=deployed,
            capital_utilization=utilization,
            strategy_capital=strategy_capitals or {},
            strategy_capacity=strategy_capacities or {},
            strategy_capacity_utilization=strategy_utils or {},
            capital_efficiency=efficiency,
            risk_adjusted_capital_efficiency=risk_adj_efficiency,
            marginal_capital_efficiency=marginal_efficiency,
            capital_allocation_changes_total=self._allocation_changes,
            capital_reallocation_total=self._reallocations,
            capital_guard_rejections_total=self._guard_rejections,
            capital_stress_events_total=self._stress_events,
        )
