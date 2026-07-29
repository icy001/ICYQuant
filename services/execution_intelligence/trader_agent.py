from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStyle(str, Enum):
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    VWAP = "vwap"
    TWAP = "twap"
    POV = "pov"
    ADAPTIVE = "adaptive"


class MarketCondition(str, Enum):
    NORMAL = "normal"
    VOLATILE = "volatile"
    ILLIQUID = "illiquid"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    NEWS_DRIVEN = "news_driven"


@dataclass
class OrderIntent:
    symbol: str
    side: str  # BUY / SELL
    quantity: int
    order_type: str = "LIMIT"
    limit_price: Optional[float] = None
    urgency: str = "NORMAL"  # LOW / NORMAL / HIGH
    max_slippage_bps: float = 10.0
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionDecision:
    style: ExecutionStyle
    market_condition: MarketCondition
    splits: int
    duration_minutes: int
    participation_rate: float
    venue_preference: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class AIExecutionTrader:
    """AI Execution Trader Agent - simulates institutional execution trader behavior."""

    def __init__(self):
        self.default_style = ExecutionStyle.ADAPTIVE

    def decide(self, order):
        """Decide execution strategy based on order intent and market conditions.

        Args:
            order: Order intent - can be OrderIntent dataclass or dict/symbol string.

        Returns:
            Dict containing the execution plan.
        """
        if isinstance(order, OrderIntent):
            return self._decide_from_intent(order)
        return {"execution_plan": order}

    def _decide_from_intent(self, order: OrderIntent) -> dict:
        return {
            "execution_plan": {
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "style": self.default_style.value,
                "splits": self._calculate_splits(order),
                "max_slippage_bps": order.max_slippage_bps,
            }
        }

    def _calculate_splits(self, order: OrderIntent) -> int:
        if order.quantity >= 10000:
            return 20
        elif order.quantity >= 1000:
            return 10
        elif order.quantity >= 100:
            return 5
        return 1

    def assess_condition(self, market_data: dict) -> MarketCondition:
        """Assess current market condition for execution planning."""
        volatility = market_data.get("volatility", 0)
        spread = market_data.get("spread_bps", 0)
        volume = market_data.get("volume", 0)

        if volatility > 0.03:
            return MarketCondition.VOLATILE
        if spread > 50:
            return MarketCondition.ILLIQUID
        return MarketCondition.NORMAL

    def choose_style(self, condition: MarketCondition, urgency: str) -> ExecutionStyle:
        """Choose execution style based on market condition and urgency."""
        if urgency == "HIGH":
            return ExecutionStyle.AGGRESSIVE
        if condition == MarketCondition.ILLIQUID:
            return ExecutionStyle.PASSIVE
        return ExecutionStyle.ADAPTIVE
