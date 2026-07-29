"""Portfolio Rebalancing Engine.

Triggered by cash flows (inflow/outflow) or drift from target
weights, this engine generates rebalance orders for the Execution
Engine.

Flow
----
    Cash Inflow / Outflow
        ↓
    Target Weights
        ↓
    Calculate Drift
        ↓
    Generate Orders
        ↓
    Execution Engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.fund.models import (
    Fund,
    RebalancePlan,
    RebalanceTrigger,
)


class RebalanceEngine:
    """Generates rebalance plans based on target weights and cash flows.

    Usage::

        engine = RebalanceEngine()
        plan = engine.rebalance(
            fund=fund,
            target_weights={"AI_Momentum": 0.40, "Macro": 0.30, "Cash": 0.30},
            current_allocations={"AI_Momentum": 200_000_000, "Macro": 150_000_000, "Cash": 50_000_000},
            new_cash=50_000_000,
            trigger=RebalanceTrigger.INFLOW,
        )
    """

    def __init__(self, drift_threshold: float = 0.05):
        """
        Parameters
        ----------
        drift_threshold : float
            Max allowed weight drift before rebalance is triggered (5% default).
        """
        self.drift_threshold = drift_threshold

    def rebalance(
        self,
        fund: Fund,
        target_weights: Dict[str, float],
        current_allocations: Dict[str, float],
        new_cash: float = 0.0,
        trigger: RebalanceTrigger = RebalanceTrigger.SCHEDULED,
        prices: Optional[Dict[str, float]] = None,
    ) -> RebalancePlan:
        """Generate a rebalance plan.

        Parameters
        ----------
        fund : Fund
            The fund aggregate.
        target_weights : dict
            Strategy → target weight (sum to 1.0).
        current_allocations : dict
            Strategy → current notional value.
        new_cash : float
            Additional cash to deploy (subscription inflow).
        trigger : RebalanceTrigger
            What triggered the rebalance.
        prices : dict, optional
            Strategy → current price for share quantity calculation.

        Returns
        -------
        RebalancePlan
        """
        # Validate weights
        weight_sum = sum(target_weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(f"Target weights must sum to 1.0, got {weight_sum}")

        # Calculate total portfolio
        total_current = sum(current_allocations.values()) + new_cash
        if total_current <= 0:
            raise ValueError("Total portfolio value must be positive")

        # Create plan
        plan = RebalancePlan(
            fund_id=fund.fund_id,
            trigger=trigger,
            target_weights=dict(target_weights),
            new_cash=new_cash,
        )

        # Calculate current weights
        plan.current_weights = {}
        for strategy, value in current_allocations.items():
            plan.current_weights[strategy] = value / total_current if total_current > 0 else 0.0

        # Calculate target allocations
        target_allocations: Dict[str, float] = {}
        for strategy, weight in target_weights.items():
            target_allocations[strategy] = weight * total_current

        # Generate orders
        for strategy in set(list(target_allocations.keys()) + list(current_allocations.keys())):
            target = target_allocations.get(strategy, 0.0)
            current = current_allocations.get(strategy, 0.0)
            diff = target - current

            if abs(diff) < 1.0:  # negligible
                continue

            price = prices.get(strategy, 1.0) if prices else 1.0
            quantity = diff / price if price > 0 else 0.0

            if diff > 0:
                side = "BUY"
            else:
                side = "SELL"
                quantity = abs(quantity)

            plan.add_order(
                strategy=strategy,
                symbol=strategy,  # simplified; real system maps strategy → symbols
                side=side,
                quantity=round(quantity, 2),
                price=price,
            )
            plan.estimated_cost += abs(diff)

        return plan

    def check_drift(
        self,
        target_weights: Dict[str, float],
        current_weights: Dict[str, float],
    ) -> Tuple[bool, float, Dict[str, float]]:
        """Check if portfolio has drifted beyond threshold.

        Returns
        -------
        (needs_rebalance, max_drift, drift_map)
        """
        drift_map: Dict[str, float] = {}
        max_drift = 0.0

        for strategy in set(list(target_weights.keys()) + list(current_weights.keys())):
            target = target_weights.get(strategy, 0.0)
            current = current_weights.get(strategy, 0.0)
            drift = abs(target - current)
            drift_map[strategy] = drift
            max_drift = max(max_drift, drift)

        needs_rebalance = max_drift > self.drift_threshold
        return needs_rebalance, max_drift, drift_map

    def simple_inflow_rebalance(
        self,
        fund: Fund,
        target_weights: Dict[str, float],
        current_allocations: Dict[str, float],
        inflow_amount: float,
    ) -> RebalancePlan:
        """Rebalance driven by new subscription inflow."""
        return self.rebalance(
            fund=fund,
            target_weights=target_weights,
            current_allocations=current_allocations,
            new_cash=inflow_amount,
            trigger=RebalanceTrigger.INFLOW,
        )

    def simple_outflow_rebalance(
        self,
        fund: Fund,
        target_weights: Dict[str, float],
        current_allocations: Dict[str, float],
        outflow_amount: float,
    ) -> RebalancePlan:
        """Rebalance driven by redemption outflow.

        Raises cash by selling proportionally across strategies.
        """
        return self.rebalance(
            fund=fund,
            target_weights=target_weights,
            current_allocations=current_allocations,
            new_cash=-outflow_amount,
            trigger=RebalanceTrigger.OUTFLOW,
        )
