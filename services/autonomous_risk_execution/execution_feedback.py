"""
Execution Feedback — post-execution analysis and learning pipeline.

Collects execution results and feeds them back into:
    - Execution Learning (strategy optimization)
    - Execution Memory (historical record)
    - Execution Quality (score computation)
    - Cost Model Calibration (parameter updates)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExecutionFeedbackData:
    """Complete execution feedback data."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    execution_id: str = ""

    # Pre-trade
    decision_price: float = 0.0
    arrival_price: float = 0.0
    target_quantity: int = 0

    # Execution
    avg_execution_price: float = 0.0
    filled_quantity: int = 0
    unfilled_quantity: int = 0
    execution_time_seconds: float = 0.0
    num_child_orders: int = 0

    # Costs
    commission: float = 0.0
    slippage_bps: float = 0.0
    spread_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    total_cost_bps: float = 0.0

    # Quality
    fill_rate: float = 0.0
    implementation_shortfall_bps: float = 0.0

    strategy: str = ""
    venue: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionFeedback:
    """
    Post-execution feedback collection and routing.

    Workflow:
        1. Collect fill data from broker/exchange
        2. Compute realized costs vs estimates
        3. Update execution quality scores
        4. Feed into learning system
        5. Update cost model parameters
    """

    def __init__(self) -> None:
        self._feedback_buffer: list[ExecutionFeedbackData] = []
        self._total_orders_processed: int = 0

    async def process_fills(
        self, order_id: str, fills: list[dict],
        arrival_price: float, decision_price: float,
        strategy: str = "", venue: str = "",
    ) -> ExecutionFeedbackData:
        """Process fills and generate feedback."""
        if not fills:
            return ExecutionFeedbackData(order_id=order_id)

        total_qty = sum(f.get("quantity", 0) for f in fills)
        if total_qty <= 0:
            return ExecutionFeedbackData(order_id=order_id)

        # Average execution price
        total_notional = sum(
            f.get("quantity", 0) * f.get("price", 0) for f in fills
        )
        avg_price = total_notional / total_qty if total_qty > 0 else 0

        # Slippage
        slippage_bps = 0.0
        if arrival_price > 0:
            slippage_bps = (avg_price - arrival_price) / arrival_price * 10000

        # Implementation shortfall
        shortfall = 0.0
        if decision_price > 0:
            shortfall = (avg_price - decision_price) / decision_price * 10000

        feedback = ExecutionFeedbackData(
            order_id=order_id,
            execution_id=str(uuid4()),
            decision_price=decision_price,
            arrival_price=arrival_price,
            target_quantity=total_qty,
            avg_execution_price=avg_price,
            filled_quantity=total_qty,
            num_child_orders=len(fills),
            slippage_bps=slippage_bps,
            implementation_shortfall_bps=shortfall,
            strategy=strategy,
            venue=venue,
        )

        self._feedback_buffer.append(feedback)
        self._total_orders_processed += 1

        if len(self._feedback_buffer) > 1000:
            self._feedback_buffer = self._feedback_buffer[-500:]

        logger.debug(
            "Feedback: order=%s slippage=%.1fbps shortfall=%.1fbps",
            order_id, slippage_bps, shortfall,
        )
        return feedback

    async def get_recent_feedback(self, limit: int = 20) -> list[ExecutionFeedbackData]:
        """Get recent execution feedback."""
        return self._feedback_buffer[-limit:]

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate execution statistics."""
        if not self._feedback_buffer:
            return {}

        slippages = [f.slippage_bps for f in self._feedback_buffer]
        shortfalls = [f.implementation_shortfall_bps for f in self._feedback_buffer]

        return {
            "total_orders": self._total_orders_processed,
            "avg_slippage_bps": sum(slippages) / len(slippages),
            "avg_shortfall_bps": sum(shortfalls) / len(shortfalls),
            "max_slippage_bps": max(slippages) if slippages else 0,
            "min_slippage_bps": min(slippages) if slippages else 0,
        }

    @property
    def total_processed(self) -> int:
        return self._total_orders_processed
