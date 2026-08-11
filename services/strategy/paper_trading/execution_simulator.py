"""
Execution Simulator
===================
Simulates order execution through the full virtual pipeline:

    Order → Queue → Matching → Slippage → Fill
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FillDetail:
    """A single fill from simulated execution."""
    quantity: float = 0.0
    price: float = 0.0
    slippage: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionResult:
    """Result of simulated order execution."""
    order_id: str = ""
    status: str = "pending"    # filled / partial / rejected / cancelled
    fills: List[FillDetail] = field(default_factory=list)
    total_quantity: float = 0.0
    avg_price: float = 0.0
    slippage: float = 0.0
    slippage_bps: float = 0.0
    commission: float = 0.0
    latency_ms: float = 0.0
    market_impact_bps: float = 0.0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionSimulator:
    """Simulates full order execution lifecycle.

    Orchestrates: Matching → Slippage → Commission → Latency → Impact
    """

    def __init__(self):
        self._matching_engine: Optional["MatchingEngine"] = None
        self._slippage_simulator: Optional["SlippageSimulator"] = None
        self._commission_simulator: Optional["CommissionSimulator"] = None
        self._latency_simulator: Optional["LatencySimulator"] = None
        self._liquidity_simulator: Optional["LiquiditySimulator"] = None
        self._market_impact_simulator: Optional["MarketImpactSimulator"] = None
        self._virtual_exchange: Optional["VirtualExchange"] = None
        self.is_initialized = False

    def wire(
        self,
        matching_engine: Optional[Any] = None,
        slippage_simulator: Optional[Any] = None,
        commission_simulator: Optional[Any] = None,
        latency_simulator: Optional[Any] = None,
        liquidity_simulator: Optional[Any] = None,
        market_impact_simulator: Optional[Any] = None,
        virtual_exchange: Optional[Any] = None,
    ) -> None:
        self._matching_engine = matching_engine
        self._slippage_simulator = slippage_simulator
        self._commission_simulator = commission_simulator
        self._latency_simulator = latency_simulator
        self._liquidity_simulator = liquidity_simulator
        self._market_impact_simulator = market_impact_simulator
        self._virtual_exchange = virtual_exchange

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("ExecutionSimulator initialized")

    # ------------------------------------------------------------------
    # Simulate
    # ------------------------------------------------------------------

    async def simulate_execution(self, order: Any) -> ExecutionResult:
        """Simulate full execution of an order through the pipeline."""
        start_time = datetime.now(timezone.utc)

        result = ExecutionResult(order_id=getattr(order, 'order_id', ''))

        instrument = getattr(order, 'instrument', '')
        side = getattr(order, 'side', 'BUY')
        quantity = getattr(order, 'quantity', 0.0)
        order_type = getattr(order, 'order_type', 'MARKET')
        limit_price = getattr(order, 'limit_price', None)

        # Step 1: Latency simulation
        latency_ms = 0.0
        if self._latency_simulator:
            latency_result = await self._latency_simulator.simulate()
            latency_ms = latency_result.latency_ms

        # Step 2: Matching
        match_price = 0.0
        if self._virtual_exchange:
            match = self._virtual_exchange.match_order(
                instrument, side, quantity, limit_price, order_type
            )
            match_price = match.get("price", 0.0)
            filled_qty = match.get("filled", quantity)
        else:
            match_price = getattr(order, 'price', 100.0) or 100.0
            filled_qty = quantity

        if filled_qty <= 0 or match_price <= 0:
            result.status = "rejected"
            result.execution_time_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            return result

        # Step 3: Liquidity (partial fill)
        if self._liquidity_simulator and filled_qty > 0:
            liq_result = await self._liquidity_simulator.simulate(
                instrument, filled_qty
            )
            filled_qty = liq_result.fillable_quantity

        # Step 4: Market impact
        impact_bps = 0.0
        if self._market_impact_simulator:
            impact_result = await self._market_impact_simulator.simulate(
                instrument, filled_qty, match_price
            )
            impact_bps = impact_result.impact_bps

        # Step 5: Slippage
        slippage_total = 0.0
        if self._slippage_simulator:
            slip_result = await self._slippage_simulator.simulate(
                instrument, match_price, filled_qty, side
            )
            slippage_total = slip_result.slippage_amount

        # Step 6: Commission
        commission = 0.0
        if self._commission_simulator:
            comm_result = await self._commission_simulator.calculate(
                match_price, filled_qty
            )
            commission = comm_result.commission

        # Build fill
        fill_price = match_price + (slippage_total / filled_qty if filled_qty > 0 else 0)
        fill = FillDetail(
            quantity=filled_qty,
            price=fill_price,
            slippage=slippage_total,
        )

        result.fills = [fill]
        result.total_quantity = filled_qty
        result.avg_price = fill_price
        result.slippage = slippage_total
        result.slippage_bps = (
            (abs(slippage_total) / match_price * 10000) if match_price > 0 else 0.0
        )
        result.commission = commission
        result.latency_ms = latency_ms
        result.market_impact_bps = impact_bps
        result.status = "filled" if filled_qty >= quantity else "partial"

        result.execution_time_ms = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        logger.debug("Simulated execution: %s fill=%s price=%s slip=%s",
                      result.order_id, result.total_quantity,
                      round(result.avg_price, 4), round(result.slippage, 4))
        return result

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "is_initialized": self.is_initialized,
            "has_matching": self._matching_engine is not None,
            "has_slippage": self._slippage_simulator is not None,
            "has_commission": self._commission_simulator is not None,
            "has_latency": self._latency_simulator is not None,
            "has_liquidity": self._liquidity_simulator is not None,
            "has_market_impact": self._market_impact_simulator is not None,
        }
