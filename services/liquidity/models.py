"""Liquidity & Market Impact Engine — Core Domain Models.

Defines the data structures for:
- OrderBook (L1/L2 bid-ask depth)
- LiquidityScore (composite scoring)
- MarketDepth (depth analysis)
- ImpactEstimate (market impact prediction)
- CapacityEstimate (strategy capacity)
- ImbalanceAnalysis (bid/ask pressure)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================


class Side(str, Enum):
    """Order or order-book side.

    Used for both order direction (BUY/SELL) and
    order book side (BID/ASK).
    """

    BID = "BID"
    ASK = "ASK"
    BUY = "BUY"
    SELL = "SELL"


class LiquidityGrade(str, Enum):
    """Liquidity quality grade."""

    EXCELLENT = "EXCELLENT"    # 90-100
    GOOD = "GOOD"              # 70-90
    NORMAL = "NORMAL"          # 50-70
    POOR = "POOR"              # 30-50
    AVOID = "AVOID"            # 0-30


class MarketCondition(str, Enum):
    """Market microstructure condition."""

    BALANCED = "BALANCED"
    BUY_PRESSURE = "BUY_PRESSURE"
    SELL_PRESSURE = "SELL_PRESSURE"
    EXTREME_BUY = "EXTREME_BUY"
    EXTREME_SELL = "EXTREME_SELL"


class CapacityLevel(str, Enum):
    """Strategy capacity level."""

    HIGH = "HIGH"            # > 2x current
    ADEQUATE = "ADEQUATE"    # 1x - 2x current
    CONSTRAINED = "CONSTRAINED"  # 0.5x - 1x
    LIMITED = "LIMITED"      # < 0.5x


class DepthLevel(str, Enum):
    """Market depth quality."""

    DEEP = "DEEP"            # > 50x order at best
    MODERATE = "MODERATE"    # 10x - 50x
    SHALLOW = "SHALLOW"      # 2x - 10x
    THIN = "THIN"            # < 2x


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class PriceLevel:
    """A single price level in the order book.

    Contains the price and total quantity available at that level.
    """

    price: float
    volume: float
    order_count: int = 0  # Number of orders at this level (L2 detail)

    @property
    def notional(self) -> float:
        """Total notional value at this level."""
        return self.price * self.volume

    def to_dict(self) -> dict:
        return {
            "price": round(self.price, 4),
            "volume": round(self.volume, 2),
            "order_count": self.order_count,
            "notional": round(self.notional, 2),
        }


@dataclass
class OrderBook:
    """Limit order book snapshot.

    Maintains the full bid/ask depth with multiple price levels.
    Supports L1 (top of book), L2 (aggregated by price), and
    full order book data.

    Example:
        book = OrderBook(
            symbol="NVDA",
            bids=[PriceLevel(150.0, 5000), PriceLevel(149.98, 8000)],
            asks=[PriceLevel(150.02, 3000), PriceLevel(150.04, 6000)],
        )
    """

    symbol: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    bids: List[PriceLevel] = field(default_factory=list)
    asks: List[PriceLevel] = field(default_factory=list)

    # Market reference
    last_price: float = 0.0
    daily_volume: float = 0.0
    adv: float = 0.0  # Average daily volume

    def __post_init__(self) -> None:
        if self.bids:
            self.bids.sort(key=lambda x: x.price, reverse=True)
        if self.asks:
            self.asks.sort(key=lambda x: x.price)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def best_bid(self) -> Optional[PriceLevel]:
        """Highest bid price level."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[PriceLevel]:
        """Lowest ask price level."""
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float:
        """Mid price (average of best bid and ask)."""
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return (bb.price + ba.price) / 2
        if bb:
            return bb.price
        if ba:
            return ba.price
        return self.last_price

    @property
    def spread(self) -> float:
        """Absolute spread (ask - bid)."""
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return ba.price - bb.price
        return 0.0

    @property
    def spread_bps(self) -> float:
        """Spread in basis points relative to mid price."""
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 10000
        return 0.0

    @property
    def total_bid_volume(self) -> float:
        """Total volume on the bid side (all levels)."""
        return sum(b.volume for b in self.bids)

    @property
    def total_ask_volume(self) -> float:
        """Total volume on the ask side (all levels)."""
        return sum(a.volume for a in self.asks)

    @property
    def bid_depth_5(self) -> float:
        """Bid volume within top 5 levels."""
        return sum(b.volume for b in self.bids[:5])

    @property
    def ask_depth_5(self) -> float:
        """Ask volume within top 5 levels."""
        return sum(a.volume for a in self.asks[:5])

    @property
    def imbalance_ratio(self) -> float:
        """Bid/Ask volume imbalance: bid_total / (bid_total + ask_total).

        > 0.5 = buy pressure, < 0.5 = sell pressure.
        """
        total = self.total_bid_volume + self.total_ask_volume
        if total > 0:
            return self.total_bid_volume / total
        return 0.5

    @property
    def weighted_bid_price(self) -> float:
        """Volume-weighted average bid price."""
        total_vol = self.total_bid_volume
        if total_vol > 0:
            return sum(b.price * b.volume for b in self.bids) / total_vol
        return 0.0

    @property
    def weighted_ask_price(self) -> float:
        """Volume-weighted average ask price."""
        total_vol = self.total_ask_volume
        if total_vol > 0:
            return sum(a.price * a.volume for a in self.asks) / total_vol
        return 0.0

    @property
    def level_count(self) -> int:
        """Number of price levels per side."""
        return max(len(self.bids), len(self.asks))

    def get_bid_volume_at_depth(self, levels: int = 5) -> float:
        """Get cumulative bid volume within N levels."""
        return sum(b.volume for b in self.bids[:levels])

    def get_ask_volume_at_depth(self, levels: int = 5) -> float:
        """Get cumulative ask volume within N levels."""
        return sum(a.volume for a in self.asks[:levels])

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "last_price": self.last_price,
            "daily_volume": self.daily_volume,
            "adv": self.adv,
            "best_bid": self.best_bid.price if self.best_bid else None,
            "best_ask": self.best_ask.price if self.best_ask else None,
            "mid_price": round(self.mid_price, 4),
            "spread": round(self.spread, 4),
            "spread_bps": round(self.spread_bps, 2),
            "total_bid_volume": round(self.total_bid_volume, 2),
            "total_ask_volume": round(self.total_ask_volume, 2),
            "imbalance_ratio": round(self.imbalance_ratio, 4),
            "bid_depth_5": round(self.bid_depth_5, 2),
            "ask_depth_5": round(self.ask_depth_5, 2),
            "level_count": self.level_count,
            "bids": [b.to_dict() for b in self.bids[:5]],
            "asks": [a.to_dict() for a in self.asks[:5]],
        }


@dataclass
class LiquidityScore:
    """Composite liquidity quality score.

    Computed from depth, spread tightness, turnover, and fill probability.

    Scoring:
        90-100  EXCELLENT
        70-90   GOOD
        50-70   NORMAL
        30-50   POOR
        0-30    AVOID
    """

    symbol: str
    score: float = 0.0                    # 0-100 composite score
    grade: LiquidityGrade = LiquidityGrade.NORMAL

    # Component scores (all 0-100)
    depth_score: float = 0.0              # Based on order book depth
    spread_score: float = 0.0             # Based on bid-ask spread narrowness
    turnover_score: float = 0.0           # Based on trading volume
    fill_probability: float = 0.0         # Likelihood of execution at target size

    # Raw metrics
    spread_bps: float = 0.0
    depth_at_best: float = 0.0
    daily_volume: float = 0.0
    adv: float = 0.0
    volatility: float = 0.0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.score > 0:
            self.grade = self._compute_grade(self.score)

    @staticmethod
    def _compute_grade(score: float) -> LiquidityGrade:
        if score >= 90:
            return LiquidityGrade.EXCELLENT
        elif score >= 70:
            return LiquidityGrade.GOOD
        elif score >= 50:
            return LiquidityGrade.NORMAL
        elif score >= 30:
            return LiquidityGrade.POOR
        return LiquidityGrade.AVOID

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "grade": self.grade.value,
            "depth_score": round(self.depth_score, 2),
            "spread_score": round(self.spread_score, 2),
            "turnover_score": round(self.turnover_score, 2),
            "fill_probability": round(self.fill_probability, 2),
            "spread_bps": round(self.spread_bps, 2),
            "depth_at_best": round(self.depth_at_best, 2),
            "daily_volume": round(self.daily_volume, 2),
            "adv": round(self.adv, 2),
            "volatility": round(self.volatility, 4),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketImpactEstimate:
    """Market impact prediction for an order.

    Computes temporary + permanent impact using microstructure
    data from the order book and market state.

    Temporary impact: dissipates over time, depends on urgency
    Permanent impact: persists, depends on total size relative to ADV
    """

    symbol: str
    order_quantity: float
    order_side: Side = Side.BUY

    # Impact estimates (in bps)
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    total_impact_bps: float = 0.0
    total_impact_pct: float = 0.0

    # Cost components
    spread_cost_bps: float = 0.0          # Half-spread cost
    expected_slippage_bps: float = 0.0    # Impact + spread
    total_cost_bps: float = 0.0           # Total execution cost

    # Context
    participation_rate: float = 0.0       # Order / ADV
    recommended_slices: int = 1
    recommended_algorithm: str = "TWAP"
    confidence: float = 0.8               # 0-1 confidence in estimate

    # Reference data
    spread_bps: float = 0.0
    adv: float = 0.0
    volatility: float = 0.0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def impact_grade(self) -> LiquidityGrade:
        """Liquidity grade based on total impact."""
        if self.total_cost_bps <= 5:
            return LiquidityGrade.EXCELLENT
        elif self.total_cost_bps <= 15:
            return LiquidityGrade.GOOD
        elif self.total_cost_bps <= 30:
            return LiquidityGrade.NORMAL
        elif self.total_cost_bps <= 60:
            return LiquidityGrade.POOR
        return LiquidityGrade.AVOID

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "order_quantity": self.order_quantity,
            "order_side": self.order_side.value,
            "temporary_impact_bps": round(self.temporary_impact_bps, 2),
            "permanent_impact_bps": round(self.permanent_impact_bps, 2),
            "total_impact_bps": round(self.total_impact_bps, 2),
            "total_impact_pct": f"{self.total_impact_pct:.3%}",
            "spread_cost_bps": round(self.spread_cost_bps, 2),
            "expected_slippage_bps": round(self.expected_slippage_bps, 2),
            "total_cost_bps": round(self.total_cost_bps, 2),
            "participation_rate": f"{self.participation_rate:.2%}",
            "recommended_slices": self.recommended_slices,
            "recommended_algorithm": self.recommended_algorithm,
            "confidence": self.confidence,
            "impact_grade": self.impact_grade.value,
        }


@dataclass
class CapacityEstimate:
    """Strategy capacity analysis.

    Estimates the maximum capital a strategy can manage without
    significantly impacting market prices.

    Key constraints:
    - Participation rate <= target (typically 10%)
    - Daily volume impact within acceptable range
    """

    strategy_id: str
    symbol: str

    # Capacity limits
    max_daily_notional: float = 0.0       # Max $ value per day
    max_single_order: float = 0.0         # Max shares per single order
    max_position_size: float = 0.0        # Max position shares

    # Current usage
    current_daily_notional: float = 0.0
    current_position: float = 0.0

    # Capacity headroom
    daily_capacity_pct: float = 0.0       # % of max daily used
    position_capacity_pct: float = 0.0    # % of max position used

    level: CapacityLevel = CapacityLevel.ADEQUATE

    # Context
    adv: float = 0.0
    target_participation: float = 0.10    # Target max participation rate
    price: float = 0.0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.max_daily_notional > 0:
            self.daily_capacity_pct = self.current_daily_notional / self.max_daily_notional
        if self.max_position_size > 0:
            self.position_capacity_pct = self.current_position / self.max_position_size
        self._compute_level()

    def _compute_level(self) -> None:
        max_pct = max(self.daily_capacity_pct, self.position_capacity_pct)
        if max_pct < 0.5:
            self.level = CapacityLevel.HIGH
        elif max_pct < 1.0:
            self.level = CapacityLevel.ADEQUATE
        elif max_pct < 2.0:
            self.level = CapacityLevel.CONSTRAINED
        else:
            self.level = CapacityLevel.LIMITED

    @property
    def can_scale(self) -> bool:
        """Whether the strategy has room to scale."""
        return self.level in (CapacityLevel.HIGH, CapacityLevel.ADEQUATE)

    @property
    def remaining_daily_capacity(self) -> float:
        """Remaining daily notional capacity."""
        return max(0.0, self.max_daily_notional - self.current_daily_notional)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "max_daily_notional": round(self.max_daily_notional, 2),
            "max_single_order": round(self.max_single_order, 2),
            "max_position_size": round(self.max_position_size, 2),
            "current_daily_notional": round(self.current_daily_notional, 2),
            "current_position": round(self.current_position, 2),
            "daily_capacity_pct": f"{self.daily_capacity_pct:.1%}",
            "position_capacity_pct": f"{self.position_capacity_pct:.1%}",
            "level": self.level.value,
            "can_scale": self.can_scale,
            "remaining_daily_capacity": round(self.remaining_daily_capacity, 2),
            "adv": round(self.adv, 2),
            "target_participation": self.target_participation,
            "price": self.price,
        }


@dataclass
class ImbalanceAnalysis:
    """Bid/Ask imbalance analysis.

    Analyzes the directional pressure in the order book and
    provides execution recommendations.
    """

    symbol: str
    imbalance_ratio: float = 0.5           # bid_vol / total_vol
    condition: MarketCondition = MarketCondition.BALANCED

    # Component metrics
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    bid_depth_5: float = 0.0
    ask_depth_5: float = 0.0

    # Weighted prices
    weighted_bid: float = 0.0
    weighted_ask: float = 0.0

    # Execution guidance
    suggested_aggressiveness: float = 0.5  # 0=purely passive, 1=maximum aggression
    suggested_urgency: str = "NORMAL"      # LOW, NORMAL, HIGH, CRITICAL
    note: str = ""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.condition = self._classify_condition(self.imbalance_ratio)

    @staticmethod
    def _classify_condition(ratio: float) -> MarketCondition:
        if ratio >= 0.8:
            return MarketCondition.EXTREME_BUY
        elif ratio >= 0.65:
            return MarketCondition.BUY_PRESSURE
        elif ratio <= 0.2:
            return MarketCondition.EXTREME_SELL
        elif ratio <= 0.35:
            return MarketCondition.SELL_PRESSURE
        return MarketCondition.BALANCED

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "imbalance_ratio": round(self.imbalance_ratio, 4),
            "condition": self.condition.value,
            "bid_volume": round(self.bid_volume, 2),
            "ask_volume": round(self.ask_volume, 2),
            "bid_depth_5": round(self.bid_depth_5, 2),
            "ask_depth_5": round(self.ask_depth_5, 2),
            "suggested_aggressiveness": round(self.suggested_aggressiveness, 2),
            "suggested_urgency": self.suggested_urgency,
            "note": self.note,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DepthAnalysis:
    """Market depth analysis result.

    Evaluates how deep the order book is and how much size
    can be executed without significant price movement.
    """

    symbol: str
    level: DepthLevel = DepthLevel.MODERATE

    # At different market impact thresholds
    volume_at_5bps: float = 0.0    # Total shares before 5bps price move
    volume_at_10bps: float = 0.0   # Total shares before 10bps price move
    volume_at_25bps: float = 0.0   # Total shares before 25bps price move
    volume_at_50bps: float = 0.0   # Total shares before 50bps price move

    # Depth quality
    depth_multiple: float = 0.0    # How many multiples of order size available at best

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.level = self._compute_level(self.depth_multiple)

    @staticmethod
    def _compute_level(multiple: float) -> DepthLevel:
        if multiple >= 50:
            return DepthLevel.DEEP
        elif multiple >= 10:
            return DepthLevel.MODERATE
        elif multiple >= 2:
            return DepthLevel.SHALLOW
        return DepthLevel.THIN

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "level": self.level.value,
            "depth_multiple": round(self.depth_multiple, 2),
            "volume_at_5bps": round(self.volume_at_5bps, 2),
            "volume_at_10bps": round(self.volume_at_10bps, 2),
            "volume_at_25bps": round(self.volume_at_25bps, 2),
            "volume_at_50bps": round(self.volume_at_50bps, 2),
            "timestamp": self.timestamp.isoformat(),
        }
