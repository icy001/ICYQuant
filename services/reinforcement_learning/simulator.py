"""Trading Simulator — realistic trade execution for RL training.

Models real-world trading constraints including commissions, slippage,
market impact, and liquidity limits to prevent unrealistic RL policies.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math
import random

import numpy as np


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    VWAP = "vwap"
    TWAP = "twap"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class SimulatorConfig:
    """Configuration for the trading simulator."""

    # Cost model
    commission_rate: float = 0.001  # 10 bps
    slippage_model: str = "linear"  # linear, square_root, power_law
    slippage_bps: float = 1.0  # base slippage
    spread_bps: float = 2.0  # bid-ask spread

    # Market impact
    impact_model: str = "almgren_chriss"  # almgren_chriss, kissell
    temporary_impact_factor: float = 0.1
    permanent_impact_factor: float = 0.05
    daily_volume_fraction_limit: float = 0.05  # max 5% of ADV

    # Liquidity
    min_fill_ratio: float = 0.95  # minimum fill of order
    max_order_value: float = 10_000_000.0

    # Latency
    latency_ms: float = 5.0  # simulated latency
    latency_jitter_ms: float = 2.0

    # Risk
    max_position_pct: float = 0.25
    max_leverage: float = 2.0
    require_risk_check: bool = True

    seed: Optional[int] = None


@dataclass
class TradeResult:
    """Result of a trade execution."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    requested_quantity: float
    filled_quantity: float
    fill_price: float
    expected_price: float
    commission: float
    slippage_cost: float
    impact_cost: float
    total_cost: float
    fill_ratio: float
    latency_ms: float
    success: bool = True
    rejection_reason: Optional[str] = None


class MarketImpactModel:
    """Models market impact of trades."""

    def __init__(self, config: SimulatorConfig):
        self.config = config

    def compute_impact(
        self,
        order_value: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """Compute market impact cost.

        Uses Almgren-Chriss model:
            Impact = temp_impact * (size / volume) + perm_impact * (size / volume)
        """
        if daily_volume <= 0:
            return 0.0

        participation_rate = order_value / daily_volume

        if self.config.impact_model == "almgren_chriss":
            temp = (
                self.config.temporary_impact_factor
                * volatility
                * math.pow(participation_rate, 0.6)
            )
            perm = (
                self.config.permanent_impact_factor
                * volatility
                * participation_rate
            )
            return temp + perm
        elif self.config.impact_model == "kissell":
            return (
                self.config.temporary_impact_factor
                * volatility
                * math.pow(participation_rate, 0.5)
            )
        else:
            return self.config.slippage_bps / 10000.0 * order_value


class TradingSimulator:
    """Realistic trading simulator for RL environments.

    Simulates trade execution with realistic costs, slippage,
    market impact, and liquidity constraints.

    Usage:
        sim = TradingSimulator(config)
        result = sim.execute_order("AAPL", OrderSide.BUY, 100, OrderType.MARKET)
    """

    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        self._rng = random.Random(self.config.seed)
        self._impact_model = MarketImpactModel(self.config)
        self._trade_history: List[TradeResult] = []

    def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        current_price: float = 100.0,
        daily_volume: float = 1_000_000.0,
        volatility: float = 0.3,
    ) -> TradeResult:
        """Execute a single order through the simulator.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Number of shares/units
            order_type: Market, limit, etc.
            limit_price: Limit price (for limit orders)
            current_price: Current market price
            daily_volume: Average daily volume
            volatility: Current volatility

        Returns:
            TradeResult with execution details
        """
        order_value = quantity * current_price

        # Latency simulation
        latency = max(
            0,
            self.config.latency_ms
            + self._rng.gauss(0, self.config.latency_jitter_ms),
        )

        # Risk check
        if self.config.require_risk_check:
            if order_value > self.config.max_order_value:
                return TradeResult(
                    symbol=symbol, side=side, order_type=order_type,
                    requested_quantity=quantity, filled_quantity=0.0,
                    fill_price=current_price, expected_price=current_price,
                    commission=0.0, slippage_cost=0.0, impact_cost=0.0,
                    total_cost=0.0, fill_ratio=0.0, latency_ms=latency,
                    success=False,
                    rejection_reason=f"Order value {order_value:.0f} exceeds max {self.config.max_order_value:.0f}",
                )

        # Liquidity constraint
        max_fill_qty = daily_volume * self.config.daily_volume_fraction_limit
        fill_qty = min(quantity, max_fill_qty)

        # Slippage
        slippage_pct = self._compute_slippage(order_value, daily_volume, volatility)
        if side == OrderSide.BUY:
            fill_price = current_price * (1 + slippage_pct + self.config.spread_bps / 20000.0)
        else:
            fill_price = current_price * (1 - slippage_pct - self.config.spread_bps / 20000.0)

        # Limit order price check
        if order_type == OrderType.LIMIT and limit_price is not None:
            if side == OrderSide.BUY and fill_price > limit_price:
                fill_qty = 0.0
            elif side == OrderSide.SELL and fill_price < limit_price:
                fill_qty = 0.0

        # Market impact cost
        impact_cost = self._impact_model.compute_impact(
            fill_qty * current_price, daily_volume, volatility
        )

        # Commission
        commission = abs(fill_qty * fill_price) * self.config.commission_rate

        # Slippage cost
        expected_price = current_price
        slippage_cost = abs(fill_qty * (fill_price - expected_price))

        total_cost = commission + slippage_cost + impact_cost
        fill_ratio = fill_qty / quantity if quantity > 0 else 0.0

        result = TradeResult(
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_quantity=quantity,
            filled_quantity=max(0, fill_qty),
            fill_price=fill_price,
            expected_price=expected_price,
            commission=commission,
            slippage_cost=slippage_cost,
            impact_cost=impact_cost,
            total_cost=total_cost,
            fill_ratio=fill_ratio,
            latency_ms=latency,
            success=fill_qty > 0,
        )

        self._trade_history.append(result)
        return result

    def execute_basket(
        self,
        orders: List[Dict[str, Any]],
        current_prices: Dict[str, float],
        daily_volumes: Dict[str, float],
        volatilities: Dict[str, float],
    ) -> List[TradeResult]:
        """Execute a basket of orders.

        Args:
            orders: List of order dicts with symbol, side, quantity, order_type
            current_prices: Current prices per symbol
            daily_volumes: ADV per symbol
            volatilities: Volatility per symbol
        """
        results = []
        for order in orders:
            symbol = order["symbol"]
            result = self.execute_order(
                symbol=symbol,
                side=order["side"],
                quantity=order["quantity"],
                order_type=order.get("order_type", OrderType.MARKET),
                limit_price=order.get("limit_price"),
                current_price=current_prices.get(symbol, 100.0),
                daily_volume=daily_volumes.get(symbol, 1_000_000.0),
                volatility=volatilities.get(symbol, 0.3),
            )
            results.append(result)
        return results

    def _compute_slippage(
        self,
        order_value: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """Compute slippage percentage."""
        if daily_volume <= 0:
            return 0.0

        participation = order_value / daily_volume

        if self.config.slippage_model == "linear":
            return self.config.slippage_bps / 10000.0 * participation
        elif self.config.slippage_model == "square_root":
            return (
                self.config.slippage_bps / 10000.0
                * math.sqrt(participation)
                * volatility
            )
        elif self.config.slippage_model == "power_law":
            return (
                self.config.slippage_bps / 10000.0
                * math.pow(participation, 0.75)
                * volatility
            )
        else:
            return self.config.slippage_bps / 10000.0

    def get_total_costs(self) -> Dict[str, float]:
        """Get cumulative cost statistics."""
        total_commission = sum(r.commission for r in self._trade_history)
        total_slippage = sum(r.slippage_cost for r in self._trade_history)
        total_impact = sum(r.impact_cost for r in self._trade_history)
        total = total_commission + total_slippage + total_impact

        return {
            "total_commission": total_commission,
            "total_slippage": total_slippage,
            "total_impact": total_impact,
            "total_cost": total,
            "num_trades": len(self._trade_history),
        }

    def reset(self):
        """Reset trade history."""
        self._trade_history = []
