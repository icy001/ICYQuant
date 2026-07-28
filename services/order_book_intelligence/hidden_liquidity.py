"""Hidden Liquidity Estimator — dark pool & hidden order detection.

Estimates hidden/undisclosed liquidity in the market through trade
pattern analysis, repeatable fill behavior, and order book dynamics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HiddenLiquidityType(str, Enum):
    """Types of hidden liquidity."""

    ICEBERG = "iceberg"  # Partially displayed order
    DARK_POOL = "dark_pool"  # Off-exchange liquidity
    HIDDEN_ORDER = "hidden_order"  # Fully hidden resting order
    RESERVE_ORDER = "reserve_order"  # Display + reserve quantity


class DetectionConfidence(str, Enum):
    """Confidence level for hidden liquidity detection."""

    LOW = "low"  # < 40% confidence
    MEDIUM = "medium"  # 40–70% confidence
    HIGH = "high"  # 70–90% confidence
    VERY_HIGH = "very_high"  # > 90% confidence


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class HiddenLiquiditySignal:
    """Single hidden liquidity detection signal.

    Attributes:
        side: BID or ASK side where hidden liquidity is suspected.
        price_zone: Estimated price range of hidden liquidity.
        estimated_volume: Estimated hidden volume.
        liquidity_type: Type of hidden liquidity.
        confidence: Detection confidence level.
        probability: Estimated probability (0–1).
        indicators: List of indicators suggesting hidden liquidity.
        timestamp: Detection time.
    """

    side: str  # "bid" or "ask"
    price_zone: tuple[float, float]  # (min, max) price
    estimated_volume: float
    liquidity_type: HiddenLiquidityType = HiddenLiquidityType.HIDDEN_ORDER
    confidence: DetectionConfidence = DetectionConfidence.MEDIUM
    probability: float = 0.5
    indicators: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_reliable(self) -> bool:
        """Whether detection confidence is high or very high."""
        return self.confidence in (DetectionConfidence.HIGH, DetectionConfidence.VERY_HIGH)


@dataclass
class HiddenLiquidityEstimate:
    """Aggregated hidden liquidity estimation result.

    Attributes:
        signals: Individual hidden liquidity signals.
        total_estimated_hidden: Total estimated hidden volume.
        buy_hidden_ratio: Fraction of hidden volume on buy side.
        sell_hidden_ratio: Fraction of hidden volume on sell side.
        dark_pool_activity: Estimated dark pool trading level.
        overall_confidence: Average detection confidence.
        timestamp: Estimation time.
    """

    signals: list[HiddenLiquiditySignal]
    total_estimated_hidden: float = 0.0
    buy_hidden_ratio: float = 0.0
    sell_hidden_ratio: float = 0.0
    dark_pool_activity: float = 0.0
    overall_confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_significant_hidden(self) -> bool:
        """Whether significant hidden liquidity is detected."""
        return self.overall_confidence > 0.6

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "signal_count": len(self.signals),
            "total_estimated_hidden": round(self.total_estimated_hidden, 2),
            "buy_hidden_ratio": round(self.buy_hidden_ratio, 4),
            "sell_hidden_ratio": round(self.sell_hidden_ratio, 4),
            "dark_pool_activity": round(self.dark_pool_activity, 4),
            "overall_confidence": round(self.overall_confidence, 4),
            "top_signals": [
                {
                    "side": s.side,
                    "price_zone": s.price_zone,
                    "estimated_volume": round(s.estimated_volume, 2),
                    "type": s.liquidity_type.value,
                    "probability": round(s.probability, 4),
                }
                for s in self.signals[:5]
            ],
        }


# ---------------------------------------------------------------------------
# HiddenLiquidityEstimator
# ---------------------------------------------------------------------------


class HiddenLiquidityEstimator:
    """Estimates hidden liquidity from visible market data.

    Analyzes trade patterns, order book refresh behavior, and fill
    characteristics to infer hidden orders, icebergs, and dark pool
    activity.

    Attributes:
        min_trade_count: Minimum trades before analysis.
        lookback_trades: Number of recent trades to analyze.
        history: Past estimation results.
    """

    # Indicators that suggest hidden liquidity
    INDICATORS = {
        "repeat_fill_same_price": "Repeated fills at same price without visible order change",
        "fill_between_spread": "Trades occurring between bid-ask spread",
        "large_trade_small_impact": "Large trade with minimal price impact",
        "order_book_replenish": "Visible volume replenishes quickly after fills",
        "midpoint_trades": "Unusual volume of midpoint trades",
        "size_discrepancy": "Trade size exceeds displayed order size",
        "cancellation_pattern": "Frequent cancel-replace at same price level",
        "time_pattern": "Regular pattern of fills at specific times",
    }

    CONFIDENCE_THRESHOLDS: dict[DetectionConfidence, float] = {
        DetectionConfidence.LOW: 0.25,
        DetectionConfidence.MEDIUM: 0.50,
        DetectionConfidence.HIGH: 0.75,
        DetectionConfidence.VERY_HIGH: 0.90,
    }

    def __init__(
        self,
        min_trade_count: int = 10,
        lookback_trades: int = 100,
    ) -> None:
        """Initialize the hidden liquidity estimator.

        Args:
            min_trade_count: Minimum trades before estimating.
            lookback_trades: Number of recent trades to analyze.
        """
        self.min_trade_count = min_trade_count
        self.lookback_trades = lookback_trades
        self.history: list[HiddenLiquidityEstimate] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def estimate(
        self,
        trades: list[dict[str, Any]],
        order_book_events: Optional[list[dict[str, Any]]] = None,
        mid_price: Optional[float] = None,
    ) -> HiddenLiquidityEstimate:
        """Estimate hidden liquidity from trade and order book data.

        Args:
            trades: List of trade dicts with keys: price, volume, side,
                    aggressor, timestamp.
            order_book_events: Optional order book update events for
                               replenishment detection.
            mid_price: Current mid price for midpoint trade detection.

        Returns:
            HiddenLiquidityEstimate with signals and metrics.
        """
        trades = trades[-self.lookback_trades:] if len(trades) > self.lookback_trades else trades
        signals: list[HiddenLiquiditySignal] = []

        if len(trades) < self.min_trade_count:
            return HiddenLiquidityEstimate(
                signals=signals,
                overall_confidence=0.0,
            )

        mid_price = mid_price or self._estimate_mid(trades)

        # Analyze trade patterns for each indicator
        indicators = self._analyze_trade_patterns(trades, order_book_events or [], mid_price)

        # Generate signals from indicators
        for price_zone, indicator_list in indicators.items():
            prob = self._compute_probability(indicator_list)
            conf = self._classify_confidence(prob)

            # Estimate volume from trade sizes in this zone
            zone_trades = [
                t for t in trades
                if price_zone[0] <= t.get("price", 0) <= price_zone[1]
            ]
            est_vol = sum(t.get("volume", 0) for t in zone_trades) * prob

            # Determine side
            buy_vol = sum(
                t.get("volume", 0) for t in zone_trades
                if t.get("aggressor", "") == "buy"
            )
            sell_vol = sum(
                t.get("volume", 0) for t in zone_trades
                if t.get("aggressor", "") == "sell"
            )
            side = "bid" if buy_vol > sell_vol else "ask"

            # Determine hidden type
            liq_type = self._infer_type(indicator_list)

            signals.append(
                HiddenLiquiditySignal(
                    side=side,
                    price_zone=price_zone,
                    estimated_volume=est_vol,
                    liquidity_type=liq_type,
                    confidence=conf,
                    probability=prob,
                    indicators=list(indicator_list),
                )
            )

        # Aggregate metrics
        total_hidden = sum(s.estimated_volume for s in signals)
        buy_hidden = sum(
            s.estimated_volume for s in signals if s.side == "bid"
        )
        sell_hidden = total_hidden - buy_hidden
        total_vol = sum(t.get("volume", 0) for t in trades)

        buy_ratio = buy_hidden / max(total_hidden, 1)
        sell_ratio = sell_hidden / max(total_hidden, 1)

        # Dark pool activity: midpoint trades / total trades
        if mid_price and total_vol > 0:
            midpoint_vol = sum(
                t.get("volume", 0) for t in trades
                if abs(t.get("price", 0) - mid_price) / max(mid_price, 0.0001) < 0.0001
            )
            dark_pool_activity = midpoint_vol / total_vol
        else:
            dark_pool_activity = 0.0

        # Overall confidence
        avg_prob = sum(s.probability for s in signals) / max(len(signals), 1) if signals else 0.0

        result = HiddenLiquidityEstimate(
            signals=signals,
            total_estimated_hidden=total_hidden,
            buy_hidden_ratio=buy_ratio,
            sell_hidden_ratio=sell_ratio,
            dark_pool_activity=dark_pool_activity,
            overall_confidence=avg_prob,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Trade Pattern Analysis
    # ------------------------------------------------------------------

    def _analyze_trade_patterns(
        self,
        trades: list[dict[str, Any]],
        order_book_events: list[dict[str, Any]],
        mid_price: float,
    ) -> dict[tuple[float, float], set[str]]:
        """Analyze trade patterns to identify hidden liquidity indicators.

        Returns:
            Dict mapping price zones to sets of indicator names.
        """
        # Group trades by price zone (cluster similar prices)
        zones: dict[tuple[float, float], set[str]] = {}

        # Build price clusters (±0.5% bands)
        price_clusters: dict[float, list[dict[str, Any]]] = {}
        for t in trades:
            p = t.get("price", 0)
            # Round to nearest 0.5% band of mid price
            band = round(p / max(mid_price * 0.005, 0.0001))
            key = round(band * mid_price * 0.005, 4)
            if key not in price_clusters:
                price_clusters[key] = []
            price_clusters[key].append(t)

        for cluster_price, cluster_trades in price_clusters.items():
            zone = (cluster_price * 0.995, cluster_price * 1.005)
            zone_indicators: set[str] = set()

            # Check: repeat fills at same price
            if len(cluster_trades) >= 3:
                zone_indicators.add("repeat_fill_same_price")

            # Check: trades between spread (near mid)
            if abs(cluster_price - mid_price) / max(mid_price, 0.0001) < 0.0005:
                zone_indicators.add("fill_between_spread")

            # Check: midpoint trades
            if abs(cluster_price - mid_price) / max(mid_price, 0.0001) < 0.0001:
                zone_indicators.add("midpoint_trades")

            # Check: size discrepancy
            avg_size = sum(t.get("volume", 0) for t in cluster_trades) / len(cluster_trades)
            if avg_size > 500:
                zone_indicators.add("large_trade_small_impact")

            # Check: time pattern (trades at regular intervals)
            timestamps = sorted([t.get("timestamp", 0) for t in cluster_trades if "timestamp" in t])
            if len(timestamps) >= 3:
                intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    if all(abs(i - avg_interval) / max(avg_interval, 0.0001) < 0.2 for i in intervals):
                        zone_indicators.add("time_pattern")

            # Check: order book replenishment from events
            replenish_count = sum(
                1 for e in order_book_events
                if abs(e.get("price", 0) - cluster_price) / max(cluster_price, 0.0001) < 0.01
                and e.get("event", "") == "add"
            )
            if replenish_count >= 3:
                zone_indicators.add("order_book_replenish")

            if zone_indicators:
                zones[zone] = zone_indicators

        return zones

    # ------------------------------------------------------------------
    # Scoring & Classification
    # ------------------------------------------------------------------

    def _compute_probability(self, indicators: set[str]) -> float:
        """Compute hidden liquidity probability from indicators.

        Args:
            indicators: Set of detected indicator names.

        Returns:
            Estimated probability (0–1).
        """
        base = 0.0
        weights = {
            "repeat_fill_same_price": 0.15,
            "fill_between_spread": 0.10,
            "large_trade_small_impact": 0.20,
            "order_book_replenish": 0.25,
            "midpoint_trades": 0.10,
            "size_discrepancy": 0.20,
            "cancellation_pattern": 0.20,
            "time_pattern": 0.15,
        }

        for ind in indicators:
            base += weights.get(ind, 0.10)

        # Diminishing returns for many indicators
        return min(0.95, base / (1.0 + 0.3 * (len(indicators) - 1)))

    def _classify_confidence(self, probability: float) -> DetectionConfidence:
        """Classify probability into confidence level."""
        for level, threshold in sorted(
            self.CONFIDENCE_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if probability >= threshold:
                return level
        return DetectionConfidence.LOW

    def _infer_type(self, indicators: set[str]) -> HiddenLiquidityType:
        """Infer hidden liquidity type from indicators."""
        if "order_book_replenish" in indicators and "repeat_fill_same_price" in indicators:
            return HiddenLiquidityType.ICEBERG
        elif "midpoint_trades" in indicators or "fill_between_spread" in indicators:
            return HiddenLiquidityType.DARK_POOL
        elif "size_discrepancy" in indicators:
            return HiddenLiquidityType.RESERVE_ORDER
        else:
            return HiddenLiquidityType.HIDDEN_ORDER

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _estimate_mid(self, trades: list[dict[str, Any]]) -> float:
        """Estimate mid price from trades."""
        prices = [t["price"] for t in trades if "price" in t]
        if not prices:
            return 0.0
        return (max(prices) + min(prices)) / 2.0

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_estimate(
        self,
        trades: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Quick hidden liquidity estimate from trades.

        Args:
            trades: Trade data.

        Returns:
            Dict with estimated hidden volume and confidence.
        """
        result = self.estimate(trades)
        return {
            "hidden_probability": round(result.overall_confidence, 4),
            "estimated_hidden_volume": round(result.total_estimated_hidden, 2),
            "dark_pool_activity": round(result.dark_pool_activity, 4),
            "signal_count": len(result.signals),
        }

    def last_result(self) -> Optional[HiddenLiquidityEstimate]:
        """Return the most recent estimation result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset estimation history."""
        self.history.clear()
