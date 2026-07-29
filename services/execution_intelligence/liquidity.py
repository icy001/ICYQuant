from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OrderBookLevel:
    price: float
    size: int
    side: str  # BID / ASK


@dataclass
class LiquiditySnapshot:
    symbol: str
    timestamp: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    spread: float
    spread_bps: float
    depth_5_levels: int
    depth_10_levels: int
    volume_1m: int
    volume_5m: int


@dataclass
class LiquidityAssessment:
    symbol: str
    liquidity_score: float  # 0-100
    liquidity_tier: str  # HIGH / MEDIUM / LOW / ILLIQUID
    spread_quality: str  # TIGHT / NORMAL / WIDE
    depth_quality: str  # DEEP / ADEQUATE / SHALLOW
    tradable_qty_1bp: int
    warnings: List[str] = field(default_factory=list)


class LiquidityDetectionEngine:
    """Liquidity Detection Engine - analyzes market liquidity conditions."""

    def __init__(self):
        self.tight_spread_threshold_bps = 5.0
        self.wide_spread_threshold_bps = 50.0

    def detect(self, market):
        """Detect liquidity conditions from market data.

        Args:
            market: Market data - can be LiquiditySnapshot dataclass or dict/symbol.

        Returns:
            Dict containing liquidity analysis.
        """
        if isinstance(market, LiquiditySnapshot):
            return self._analyze_liquidity(market)
        return {"liquidity": market}

    def _analyze_liquidity(self, snapshot: LiquiditySnapshot) -> dict:
        score = self._calculate_liquidity_score(snapshot)
        tier = self._classify_tier(score)
        spread_quality = self._classify_spread(snapshot.spread_bps)
        depth_quality = self._classify_depth(snapshot.depth_5_levels)

        tradable_qty = self._estimate_tradable_qty(snapshot)

        return {
            "liquidity": {
                "symbol": snapshot.symbol,
                "liquidity_score": score,
                "liquidity_tier": tier,
                "spread_bps": round(snapshot.spread_bps, 2),
                "spread_quality": spread_quality,
                "depth_quality": depth_quality,
                "tradable_qty_1bp": tradable_qty,
                "bid": snapshot.bid,
                "ask": snapshot.ask,
            }
        }

    def _calculate_liquidity_score(self, snapshot: LiquiditySnapshot) -> int:
        score = 50
        # Tighter spread = higher score
        if snapshot.spread_bps <= self.tight_spread_threshold_bps:
            score += 30
        elif snapshot.spread_bps <= self.wide_spread_threshold_bps:
            score += 10
        else:
            score -= 20

        # Deeper book = higher score
        if snapshot.depth_5_levels > 10000:
            score += 20
        elif snapshot.depth_5_levels > 1000:
            score += 10
        else:
            score -= 10

        return max(0, min(100, score))

    def _classify_tier(self, score: int) -> str:
        if score >= 80:
            return "HIGH"
        elif score >= 50:
            return "MEDIUM"
        elif score >= 30:
            return "LOW"
        return "ILLIQUID"

    def _classify_spread(self, spread_bps: float) -> str:
        if spread_bps <= self.tight_spread_threshold_bps:
            return "TIGHT"
        elif spread_bps <= self.wide_spread_threshold_bps:
            return "NORMAL"
        return "WIDE"

    def _classify_depth(self, depth_qty: int) -> str:
        if depth_qty > 5000:
            return "DEEP"
        elif depth_qty > 1000:
            return "ADEQUATE"
        return "SHALLOW"

    def _estimate_tradable_qty(self, snapshot: LiquiditySnapshot) -> int:
        """Estimate quantity tradable within 1bp of current price."""
        return min(snapshot.bid_size, snapshot.ask_size)

    def can_execute(self, assessment: LiquidityAssessment, order_size: int) -> bool:
        """Check if an order can be executed given current liquidity."""
        if assessment.liquidity_tier == "ILLIQUID":
            return order_size <= assessment.tradable_qty_1bp * 0.1
        return True
