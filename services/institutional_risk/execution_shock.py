"""ExecutionShock — execution failure shock simulation.

Simulates execution degradation: latency increase, slippage,
fill ratio decline, and market impact amplification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionShockResult:
    """Result of an execution shock simulation."""

    latency_increase_pct: float = 0.0
    slippage_increase_pct: float = 0.0
    fill_ratio_decline_pct: float = 0.0
    impact_increase_pct: float = 0.0

    original_execution_cost: float = 0.0
    shocked_execution_cost: float = 0.0
    cost_increase: float = 0.0

    original_fill_ratio: float = 1.0
    shocked_fill_ratio: float = 1.0

    orders_at_risk: int = 0
    unexecuted_value: float = 0.0
    slippage_loss: float = 0.0

    critical: bool = False


class ExecutionShockSimulator:
    """Simulates execution infrastructure degradation.

    Usage::

        sim = ExecutionShockSimulator()
        result = sim.simulate(
            latency_increase_pct=200.0,
            slippage_increase_pct=100.0,
            fill_ratio_decline_pct=-30.0,
            active_orders=[{"value": 5_000_000, "urgency": "high"}],
            normal_slippage_bps=5.0,
        )
    """

    def __init__(
        self,
        critical_cost_increase_pct: float = 50.0,
        critical_fill_ratio: float = 0.50,
    ):
        self._critical_cost = critical_cost_increase_pct
        self._critical_fill = critical_fill_ratio

    def simulate(
        self,
        latency_increase_pct: float,
        slippage_increase_pct: float,
        fill_ratio_decline_pct: float,
        active_orders: List[Dict[str, Any]],
        normal_slippage_bps: float = 5.0,
        normal_fill_ratio: float = 0.95,
    ) -> ExecutionShockResult:
        """Simulate an execution shock.

        Args:
            latency_increase_pct: latency increase %
            slippage_increase_pct: slippage increase %
            fill_ratio_decline_pct: fill ratio decline % (negative)
            active_orders: list of {value, urgency, ...}
            normal_slippage_bps: normal slippage in bps
            normal_fill_ratio: normal fill ratio (0-1)
        """
        import math

        total_order_value = sum(o.get("value", 0.0) for o in active_orders)

        # slippage
        slippage_factor = 1.0 + slippage_increase_pct / 100.0
        shocked_slippage_bps = normal_slippage_bps * slippage_factor

        original_cost = total_order_value * (normal_slippage_bps / 10000)
        shocked_cost = total_order_value * (shocked_slippage_bps / 10000)
        cost_increase = shocked_cost - original_cost

        # fill ratio
        fill_factor = 1.0 + fill_ratio_decline_pct / 100.0
        shocked_fill = max(0.0, min(1.0, normal_fill_ratio * fill_factor))
        unexecuted = total_order_value * (normal_fill_ratio - shocked_fill)

        # orders at risk (those that may not execute)
        orders_at_risk = sum(
            1 for o in active_orders
            if o.get("urgency", "medium") == "high"
        )

        # slippage loss = value * (shocked - normal slippage)
        slippage_loss = total_order_value * (shocked_slippage_bps - normal_slippage_bps) / 10000

        critical = (
            cost_increase / max(original_cost, 1e-9) * 100 > self._critical_cost
            or shocked_fill < self._critical_fill
        )

        return ExecutionShockResult(
            latency_increase_pct=latency_increase_pct,
            slippage_increase_pct=slippage_increase_pct,
            fill_ratio_decline_pct=fill_ratio_decline_pct,
            impact_increase_pct=slippage_increase_pct,
            original_execution_cost=original_cost,
            shocked_execution_cost=shocked_cost,
            cost_increase=cost_increase,
            original_fill_ratio=normal_fill_ratio,
            shocked_fill_ratio=shocked_fill,
            orders_at_risk=orders_at_risk,
            unexecuted_value=unexecuted,
            slippage_loss=slippage_loss,
            critical=critical,
        )
