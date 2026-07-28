"""Order Imbalance Analyzer — real-time bid/ask imbalance detection.

Computes multi-level order book imbalance scores to identify
directional pressure and predict short-term price movements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from services.order_book_intelligence.snapshot import (
    BookSide,
    OrderBookSnapshot,
    PriceLevel,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ImbalanceDirection(str, Enum):
    """Imbalance directional signal."""

    STRONG_BUY = "strong_buy"  # > 0.7
    BUY = "buy"  # 0.3 ~ 0.7
    NEUTRAL = "neutral"  # -0.3 ~ 0.3
    SELL = "sell"  # -0.7 ~ -0.3
    STRONG_SELL = "strong_sell"  # < -0.7


class ImbalanceMethod(str, Enum):
    """Imbalance calculation methods."""

    SIMPLE = "simple"  # (bid - ask) / total
    VOLUME_WEIGHTED = "volume_weighted"  # weighted by distance from mid
    DEPTH_WEIGHTED = "depth_weighted"  # weighted by level depth
    MULTI_LEVEL = "multi_level"  # composite of all levels


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ImbalanceSignal:
    """Order imbalance analysis result.

    Attributes:
        score: Imbalance score from -1.0 (heavy sell) to +1.0 (heavy buy).
        direction: Directional classification.
        bid_volume: Total bid volume analyzed.
        ask_volume: Total ask volume analyzed.
        depth_levels: Number of levels used in analysis.
        confidence: Confidence in the signal (0–1).
        pressure_ratio: Ratio of aggressive vs passive order flow.
        method: Calculation method used.
        timestamp: Analysis timestamp.
    """

    score: float
    direction: ImbalanceDirection = ImbalanceDirection.NEUTRAL
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    depth_levels: int = 5
    confidence: float = 0.0
    pressure_ratio: float = 0.0
    method: ImbalanceMethod = ImbalanceMethod.SIMPLE
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_buy_pressure(self) -> bool:
        """Whether there is net buying pressure."""
        return self.score > 0.1

    @property
    def is_sell_pressure(self) -> bool:
        """Whether there is net selling pressure."""
        return self.score < -0.1

    @property
    def is_extreme(self) -> bool:
        """Whether imbalance is extreme (> 0.8 or < -0.8)."""
        return abs(self.score) > 0.8

    @property
    def magnitude(self) -> float:
        """Absolute magnitude of imbalance."""
        return abs(self.score)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "score": round(self.score, 4),
            "direction": self.direction.value,
            "bid_volume": round(self.bid_volume, 2),
            "ask_volume": round(self.ask_volume, 2),
            "confidence": round(self.confidence, 4),
            "magnitude": round(self.magnitude, 4),
            "is_extreme": self.is_extreme,
        }


# ---------------------------------------------------------------------------
# OrderImbalanceAnalyzer
# ---------------------------------------------------------------------------


class OrderImbalanceAnalyzer:
    """Real-time order book imbalance analyzer.

    Computes multi-dimensional imbalance scores from order book
    snapshots. Supports simple, volume-weighted, depth-weighted,
    and multi-level composite methods.

    Attributes:
        method: Default calculation method.
        depth_levels: Default number of book levels to analyze.
        smoothing_window: Number of past scores to average.
        score_history: Recent imbalance scores for smoothing.
        history: Full analysis history.
    """

    DIRECTION_THRESHOLDS: dict[ImbalanceDirection, tuple[float, float]] = {
        ImbalanceDirection.STRONG_SELL: (-1.0, -0.7),
        ImbalanceDirection.SELL: (-0.7, -0.3),
        ImbalanceDirection.NEUTRAL: (-0.3, 0.3),
        ImbalanceDirection.BUY: (0.3, 0.7),
        ImbalanceDirection.STRONG_BUY: (0.7, 1.0),
    }

    def __init__(
        self,
        method: ImbalanceMethod = ImbalanceMethod.MULTI_LEVEL,
        depth_levels: int = 10,
        smoothing_window: int = 5,
    ) -> None:
        """Initialize the imbalance analyzer.

        Args:
            method: Default calculation method.
            depth_levels: Default depth levels to analyze.
            smoothing_window: Number of recent scores for EMA smoothing.
        """
        self.method = method
        self.depth_levels = depth_levels
        self.smoothing_window = smoothing_window
        self.score_history: list[float] = []
        self.history: list[ImbalanceSignal] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def calculate(
        self,
        bid_volume: float,
        ask_volume: float,
        method: Optional[ImbalanceMethod] = None,
        bid_levels: Optional[list[PriceLevel]] = None,
        ask_levels: Optional[list[PriceLevel]] = None,
        mid_price: float = 0.0,
    ) -> ImbalanceSignal:
        """Calculate order imbalance.

        Args:
            bid_volume: Total bid-side volume.
            ask_volume: Total ask-side volume.
            method: Override default calculation method.
            bid_levels: Detailed bid price levels for weighted methods.
            ask_levels: Detailed ask price levels for weighted methods.
            mid_price: Mid price for distance weighting.

        Returns:
            ImbalanceSignal with score, direction, and confidence.
        """
        method = method or self.method
        total = bid_volume + ask_volume

        if total == 0:
            score = 0.0
        elif method == ImbalanceMethod.SIMPLE:
            score = (bid_volume - ask_volume) / total
        elif method == ImbalanceMethod.VOLUME_WEIGHTED:
            score = self._volume_weighted(bid_levels, ask_levels, mid_price)
        elif method == ImbalanceMethod.DEPTH_WEIGHTED:
            score = self._depth_weighted(bid_levels, ask_levels)
        elif method == ImbalanceMethod.MULTI_LEVEL:
            score = self._multi_level_composite(
                bid_volume, ask_volume,
                bid_levels, ask_levels, mid_price,
            )
        else:
            score = (bid_volume - ask_volume) / total

        # Apply smoothing
        self.score_history.append(score)
        while len(self.score_history) > self.smoothing_window:
            self.score_history.pop(0)

        smoothed = sum(self.score_history) / len(self.score_history) if self.score_history else score

        # Classify direction
        direction = self._classify(smoothed)

        # Confidence: based on volume disparity and score magnitude
        vol_disparity = abs(bid_volume - ask_volume) / max(total, 1)
        confidence = min(1.0, (abs(smoothed) * 0.6 + vol_disparity * 0.4))

        # Pressure ratio: ratio of volume imbalance to total volume
        pressure = abs(bid_volume - ask_volume) / max(total, 1) if total > 0 else 0.0

        signal = ImbalanceSignal(
            score=smoothed,
            direction=direction,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            depth_levels=self.depth_levels,
            confidence=confidence,
            pressure_ratio=pressure,
            method=method,
        )

        self.history.append(signal)
        return signal

    def calculate_from_snapshot(
        self,
        snapshot: OrderBookSnapshot,
        method: Optional[ImbalanceMethod] = None,
    ) -> ImbalanceSignal:
        """Calculate imbalance directly from an order book snapshot.

        Args:
            snapshot: Order book snapshot.
            method: Override calculation method.

        Returns:
            ImbalanceSignal.
        """
        method = method or self.method
        bid_vol = snapshot.depth_at(self.depth_levels, BookSide.BID)
        ask_vol = snapshot.depth_at(self.depth_levels, BookSide.ASK)

        return self.calculate(
            bid_volume=bid_vol,
            ask_volume=ask_vol,
            method=method,
            bid_levels=snapshot.bids[:self.depth_levels],
            ask_levels=snapshot.asks[:self.depth_levels],
            mid_price=snapshot.mid_price,
        )

    # ------------------------------------------------------------------
    # Calculation Methods
    # ------------------------------------------------------------------

    def _volume_weighted(
        self,
        bid_levels: Optional[list[PriceLevel]],
        ask_levels: Optional[list[PriceLevel]],
        mid_price: float,
    ) -> float:
        """Volume-weighted imbalance: closer-to-mid levels have higher weight."""
        if not bid_levels or not ask_levels or mid_price == 0:
            return 0.0

        weighted_bid = 0.0
        weighted_ask = 0.0

        for level in bid_levels[:self.depth_levels]:
            distance = mid_price - level.price
            if distance > 0:
                weight = 1.0 / max(distance / mid_price, 0.0001)
                weighted_bid += level.volume * weight

        for level in ask_levels[:self.depth_levels]:
            distance = level.price - mid_price
            if distance > 0:
                weight = 1.0 / max(distance / mid_price, 0.0001)
                weighted_ask += level.volume * weight

        total_w = weighted_bid + weighted_ask
        if total_w == 0:
            return 0.0

        return (weighted_bid - weighted_ask) / total_w

    def _depth_weighted(
        self,
        bid_levels: Optional[list[PriceLevel]],
        ask_levels: Optional[list[PriceLevel]],
    ) -> float:
        """Depth-weighted: deeper levels (further from top) have lower weight."""
        if not bid_levels or not ask_levels:
            return 0.0

        weighted_bid = 0.0
        weighted_ask = 0.0

        for i, level in enumerate(bid_levels[:self.depth_levels]):
            weight = 1.0 / (i + 1)
            weighted_bid += level.volume * weight

        for i, level in enumerate(ask_levels[:self.depth_levels]):
            weight = 1.0 / (i + 1)
            weighted_ask += level.volume * weight

        total_w = weighted_bid + weighted_ask
        if total_w == 0:
            return 0.0

        return (weighted_bid - weighted_ask) / total_w

    def _multi_level_composite(
        self,
        bid_volume: float,
        ask_volume: float,
        bid_levels: Optional[list[PriceLevel]],
        ask_levels: Optional[list[PriceLevel]],
        mid_price: float,
    ) -> float:
        """Composite imbalance blending simple, VW, and depth-weighted."""
        total = bid_volume + ask_volume
        simple = (bid_volume - ask_volume) / max(total, 1)

        vw = self._volume_weighted(bid_levels, ask_levels, mid_price) if bid_levels and ask_levels else simple
        dw = self._depth_weighted(bid_levels, ask_levels) if bid_levels and ask_levels else simple

        # Weighted blend: 40% simple, 35% VW, 25% depth
        return 0.40 * simple + 0.35 * vw + 0.25 * dw

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, score: float) -> ImbalanceDirection:
        """Classify imbalance score into direction."""
        for direction, (lo, hi) in self.DIRECTION_THRESHOLDS.items():
            if lo <= score < hi or (direction == ImbalanceDirection.STRONG_BUY and score == 1.0):
                return direction
        return ImbalanceDirection.NEUTRAL

    # ------------------------------------------------------------------
    # Trend Analysis
    # ------------------------------------------------------------------

    def trend(self, window: int = 10) -> dict[str, Any]:
        """Analyze imbalance trend over recent window.

        Args:
            window: Number of recent signals to analyze.

        Returns:
            Dict with trend direction, acceleration, and reversal signals.
        """
        recent = self.history[-window:] if len(self.history) >= window else self.history

        if len(recent) < 2:
            return {"trend": "insufficient_data", "acceleration": 0.0}

        scores = [s.score for s in recent]
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        acceleration = avg_second - avg_first

        if avg_second > 0.3:
            trend = "building_buy"
        elif avg_second < -0.3:
            trend = "building_sell"
        elif abs(avg_second) < 0.15:
            trend = "fading"
        else:
            trend = "mixed"

        return {
            "trend": trend,
            "current_avg": round(avg_second, 4),
            "previous_avg": round(avg_first, 4),
            "acceleration": round(acceleration, 4),
            "window_size": len(scores),
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_analyze(
        self,
        bid_volume: float,
        ask_volume: float,
    ) -> dict[str, Any]:
        """Quick imbalance analysis with defaults.

        Args:
            bid_volume: Bid-side volume.
            ask_volume: Ask-side volume.

        Returns:
            Dict with score, direction, and summary.
        """
        signal = self.calculate(bid_volume, ask_volume)
        return {
            "score": round(signal.score, 4),
            "direction": signal.direction.value,
            "confidence": round(signal.confidence, 4),
            "is_buy_pressure": signal.is_buy_pressure,
            "is_sell_pressure": signal.is_sell_pressure,
        }

    def last_result(self) -> Optional[ImbalanceSignal]:
        """Return the most recent imbalance signal."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset analyzer state."""
        self.score_history.clear()
        self.history.clear()
