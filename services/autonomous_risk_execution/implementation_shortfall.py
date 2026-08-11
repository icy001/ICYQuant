"""
Implementation Shortfall — measures the total cost of execution.

Implementation Shortfall = Decision Price - Execution Price
    + (Unfilled Qty) * (Decision Price - Final Price)

Answers: "How much did this execution cost us in total?"

Components:
    1. Delay cost: Decision Price → Arrival Price
    2. Execution cost: Arrival Price → Execution Price
    3. Opportunity cost: Unfilled portion × price movement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ShortfallComponents:
    """Implementation shortfall decomposition."""
    delay_cost_bps: float = 0.0
    execution_cost_bps: float = 0.0
    opportunity_cost_bps: float = 0.0
    total_shortfall_bps: float = 0.0
    total_shortfall_notional: float = 0.0


@dataclass
class ImplementationShortfallResult:
    """Complete implementation shortfall analysis."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    asset: str = ""
    side: str = "BUY"

    # Prices
    decision_price: float = 0.0
    arrival_price: float = 0.0
    execution_price: float = 0.0
    final_price: float = 0.0

    # Quantities
    target_quantity: int = 0
    filled_quantity: int = 0
    unfilled_quantity: int = 0

    components: ShortfallComponents = field(default_factory=ShortfallComponents)

    timestamp: datetime = field(default_factory=datetime.now)


class ImplementationShortfall:
    """
    Implementation shortfall analysis.

    Formula:
        IS = (P_exec - P_decision) / P_decision × 10000  [bps]

    Decomposition:
        Delay = (P_arrival - P_decision) / P_decision
        Execution = (P_exec - P_arrival) / P_decision
        Opportunity = (P_final - P_decision) × unfilled_ratio / P_decision
    """

    def __init__(self) -> None:
        self._analyses: list[ImplementationShortfallResult] = []

    async def compute(
        self,
        order_id: str,
        asset: str,
        side: str,
        decision_price: float,
        arrival_price: float,
        execution_price: float,
        target_quantity: int,
        filled_quantity: int,
        final_price: Optional[float] = None,
    ) -> ImplementationShortfallResult:
        """Compute implementation shortfall."""
        result = ImplementationShortfallResult(
            order_id=order_id,
            asset=asset,
            side=side,
            decision_price=decision_price,
            arrival_price=arrival_price,
            execution_price=execution_price,
            final_price=final_price or execution_price,
            target_quantity=target_quantity,
            filled_quantity=filled_quantity,
            unfilled_quantity=target_quantity - filled_quantity,
        )

        if decision_price <= 0:
            return result

        ref = decision_price

        # Delay cost
        result.components.delay_cost_bps = (
            (arrival_price - decision_price) / ref * 10000
        )

        # Execution cost
        result.components.execution_cost_bps = (
            (execution_price - arrival_price) / ref * 10000
        )

        # Opportunity cost (unfilled)
        if target_quantity > 0 and result.unfilled_quantity > 0:
            unfilled_ratio = result.unfilled_quantity / target_quantity
            result.components.opportunity_cost_bps = (
                (result.final_price - decision_price) / ref * 10000 * unfilled_ratio
            )

        # Total shortfall
        result.components.total_shortfall_bps = (
            result.components.delay_cost_bps
            + result.components.execution_cost_bps
            + result.components.opportunity_cost_bps
        )

        # Notional cost
        result.components.total_shortfall_notional = (
            abs(filled_quantity) * abs(result.components.total_shortfall_bps / 10000)
            * decision_price
        )

        self._analyses.append(result)
        if len(self._analyses) > 500:
            self._analyses = self._analyses[-250:]

        logger.debug(
            "Shortfall: %s delay=%.1f exec=%.1f opp=%.1f total=%.1fbps",
            order_id,
            result.components.delay_cost_bps,
            result.components.execution_cost_bps,
            result.components.opportunity_cost_bps,
            result.components.total_shortfall_bps,
        )
        return result

    async def get_aggregate_stats(self) -> dict:
        """Get aggregate shortfall statistics."""
        if not self._analyses:
            return {}

        totals = [a.components.total_shortfall_bps for a in self._analyses]
        return {
            "avg_shortfall_bps": sum(totals) / len(totals),
            "max_shortfall_bps": max(totals),
            "min_shortfall_bps": min(totals),
            "total_orders": len(self._analyses),
            "total_notional_cost": sum(a.components.total_shortfall_notional for a in self._analyses),
        }
