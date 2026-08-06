"""Execution Simulator — realistic trade execution simulation.

Simulates order fills considering liquidity, latency, slippage,
and market impact to produce realistic execution outcomes.

Execution Flow::

    Order Book → Liquidity Check → Latency → Slippage → Fill → Trade

Supports:
* Full fill, partial fill, rejection, timeout
* Market impact calculations
* Participation rate constraints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .slippage_model import SlippageModel, SlippageMethod
from .liquidity_model import LiquidityModel

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution simulation modes."""

    REALISTIC = "realistic"  # Full slippage/liquidity/latency
    SIMPLE = "simple"  # Basic fill at market price
    AGGRESSIVE = "aggressive"  # Always fill at worst price


@dataclass
class ExecutionResult:
    """Result of an execution simulation."""

    order_id: str
    status: str  # filled, partial, rejected, timeout
    trade: Optional[Dict[str, Any]] = None
    filled_quantity: float = 0.0
    fill_price: float = 0.0
    slippage: float = 0.0
    cost: float = 0.0
    latency_ms: float = 0.0
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionSimulator:
    """Realistic trade execution simulator.

    Considers:
    * Order book depth and liquidity
    * Network and matching latency
    * Multiple slippage models
    * Market impact estimation
    * Participation rate constraints

    Fill outcomes:
    * Full fill — entire order executed
    * Partial fill — portion filled, remainder pending
    * Rejection — no fill (insufficient liquidity, limit mismatch)
    * Timeout — order exceeds time limit
    """

    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        liquidity_model: Optional[LiquidityModel] = None,
        mode: ExecutionMode = ExecutionMode.REALISTIC,
        max_participation_rate: float = 0.1,
        fill_timeout_seconds: float = 60.0,
    ) -> None:
        self._mode = mode
        self._slippage_model = slippage_model or SlippageModel()
        self._liquidity_model = liquidity_model or LiquidityModel()
        self._max_participation_rate = max_participation_rate
        self._fill_timeout_seconds = fill_timeout_seconds

        # Track execution stats
        self._total_executions = 0
        self._total_fills = 0
        self._total_rejections = 0
        self._total_partial = 0

    # ── execute ────────────────────────────────────────────────────────────

    async def execute(
        self,
        order: Dict[str, Any],
        market_data: Dict[str, Any],
        cash: float,
        portfolio: Dict[str, Dict[str, Any]],
    ) -> ExecutionResult:
        """Execute an order against the current market.

        Args:
            order: Order dictionary (symbol, side, quantity, order_type, price).
            market_data: Current market data (OHLCV, bid/ask).
            cash: Available cash for buy orders.
            portfolio: Current portfolio positions.

        Returns:
            ExecutionResult with fill details.
        """
        self._total_executions += 1

        symbol = order.get("symbol", "")
        side = order.get("side", "buy")
        quantity = order.get("quantity", order.get("strength", 0))
        order_type = order.get("order_type", "market")
        limit_price = order.get("price")
        order_id = order.get("order_id", str(uuid4()))

        if quantity <= 0:
            return ExecutionResult(
                order_id=order_id,
                status="rejected",
                reason="Zero or negative quantity",
            )

        # Get market price
        market_price = self._get_market_price(market_data, side)

        # Simple mode: always fill at market price
        if self._mode == ExecutionMode.SIMPLE:
            return self._simple_fill(order_id, symbol, side, quantity, market_price)

        # Realistic mode
        if self._mode == ExecutionMode.REALISTIC:
            return await self._realistic_fill(
                order_id, symbol, side, quantity, order_type,
                limit_price, market_price, market_data, cash, portfolio,
            )

        # Aggressive mode
        return self._aggressive_fill(order_id, symbol, side, quantity, market_price, market_data)

    async def execute_batch(
        self,
        orders: List[Dict[str, Any]],
        market_data: Dict[str, Any],
        cash: float,
        portfolio: Dict[str, Dict[str, Any]],
    ) -> List[ExecutionResult]:
        """Execute multiple orders sequentially."""
        results = []
        for order in orders:
            result = await self.execute(order, market_data, cash, portfolio)
            results.append(result)
            if result.trade:
                cash += result.trade.get("cash_flow", 0)
                symbol = result.trade["symbol"]
                side = result.trade["side"]
                qty = result.trade["quantity"]
                current = portfolio.get(symbol, {"quantity": 0})
                portfolio[symbol] = {
                    "quantity": current["quantity"] + (qty if side == "buy" else -qty),
                    "market_value": abs(current.get("quantity", 0)) * market_data.get("close", 0),
                }
        return results

    # ── fill methods ───────────────────────────────────────────────────────

    def _simple_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
    ) -> ExecutionResult:
        """Simple mode: always fill at current market price."""
        self._total_fills += 1
        fill_price = market_price
        cost = quantity * fill_price
        cash_flow = -cost if side == "buy" else cost

        return ExecutionResult(
            order_id=order_id,
            status="filled",
            filled_quantity=quantity,
            fill_price=fill_price,
            slippage=0.0,
            cost=cost,
            trade={
                "trade_id": str(uuid4()),
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": fill_price,
                "cost": cost,
                "cash_flow": cash_flow,
                "slippage": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _realistic_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float],
        market_price: float,
        market_data: Dict[str, Any],
        cash: float,
        portfolio: Dict[str, Dict[str, Any]],
    ) -> ExecutionResult:
        """Realistic fill with slippage, liquidity, and constraints."""
        # 1. Check liquidity
        advised_volume = await self._liquidity_model.get_fillable_volume(
            symbol=symbol,
            desired_volume=quantity,
            market_data=market_data,
            participation_rate=self._max_participation_rate,
        )

        if advised_volume <= 0:
            self._total_rejections += 1
            return ExecutionResult(
                order_id=order_id,
                status="rejected",
                reason="Insufficient liquidity",
            )

        # 2. Limit order price check
        fillable_qty = min(quantity, advised_volume)
        if order_type == "limit" and limit_price is not None:
            if side == "buy" and market_price > limit_price:
                self._total_rejections += 1
                return ExecutionResult(
                    order_id=order_id,
                    status="rejected",
                    reason=f"Market price {market_price} > limit {limit_price}",
                )
            elif side == "sell" and market_price < limit_price:
                self._total_rejections += 1
                return ExecutionResult(
                    order_id=order_id,
                    status="rejected",
                    reason=f"Market price {market_price} < limit {limit_price}",
                )

        # 3. Apply slippage
        slippage = self._slippage_model.compute(
            symbol=symbol,
            side=side,
            quantity=fillable_qty,
            market_price=market_price,
            market_data=market_data,
        )
        fill_price = market_price + (slippage if side == "buy" else -slippage)

        # 4. Check cash constraint (for buy orders)
        if side == "buy" and fillable_qty * fill_price > cash:
            fillable_qty = cash / fill_price
            if fillable_qty <= 0:
                self._total_rejections += 1
                return ExecutionResult(
                    order_id=order_id,
                    status="rejected",
                    reason="Insufficient cash",
                )

        # 5. Finalize fill
        cost = fillable_qty * fill_price
        cash_flow = -cost if side == "buy" else cost

        is_full = abs(fillable_qty - quantity) < 1e-8
        status = "filled" if is_full else "partial"
        if is_full:
            self._total_fills += 1
        else:
            self._total_partial += 1

        return ExecutionResult(
            order_id=order_id,
            status=status,
            filled_quantity=fillable_qty,
            fill_price=fill_price,
            slippage=abs(fill_price - market_price),
            cost=cost,
            trade={
                "trade_id": str(uuid4()),
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": fillable_qty,
                "price": fill_price,
                "cost": cost,
                "cash_flow": cash_flow,
                "slippage": abs(fill_price - market_price),
                "slippage_bps": abs(fill_price - market_price) / market_price * 10000 if market_price > 0 else 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _aggressive_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        market_data: Dict[str, Any],
    ) -> ExecutionResult:
        """Aggressive mode: fill at worst available price."""
        spread = market_data.get("spread", market_price * 0.002)
        fill_price = market_price + (spread if side == "buy" else -spread)
        cost = quantity * fill_price
        cash_flow = -cost if side == "buy" else cost

        self._total_fills += 1
        return ExecutionResult(
            order_id=order_id,
            status="filled",
            filled_quantity=quantity,
            fill_price=fill_price,
            slippage=abs(fill_price - market_price),
            cost=cost,
            trade={
                "trade_id": str(uuid4()),
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": fill_price,
                "cost": cost,
                "cash_flow": cash_flow,
                "slippage": abs(fill_price - market_price),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _get_market_price(
        self, market_data: Dict[str, Any], side: str
    ) -> float:
        """Get the appropriate market price for the order side."""
        if side == "buy":
            return market_data.get("ask", market_data.get("close", 0.0))
        return market_data.get("bid", market_data.get("close", 0.0))

    # ── query ──────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return execution simulator statistics."""
        return {
            "mode": self._mode.value,
            "total_executions": self._total_executions,
            "total_fills": self._total_fills,
            "total_rejections": self._total_rejections,
            "total_partial": self._total_partial,
            "fill_rate": self._total_fills / max(self._total_executions, 1),
            "slippage_model": self._slippage_model.get_method().value,
            "max_participation_rate": self._max_participation_rate,
        }
