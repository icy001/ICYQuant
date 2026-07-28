"""Queue Position Estimator — predict order fill probability & ETA.

Estimates an order's position in the exchange queue and predicts
expected fill time based on trade rate, queue depth, and order
book dynamics. Essential for TWAP/VWAP execution optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QueuePosition(str, Enum):
    """Order position in the exchange queue."""

    FRONT = "front"  # Top 10% of queue
    MIDDLE = "middle"  # Middle 30–70%
    BACK = "back"  # Bottom 70–100%
    UNKNOWN = "unknown"


class FillProbability(str, Enum):
    """Fill probability classification."""

    VERY_HIGH = "very_high"  # > 90%
    HIGH = "high"  # 70–90%
    MODERATE = "moderate"  # 40–70%
    LOW = "low"  # 10–40%
    VERY_LOW = "very_low"  # < 10%


class ExecutionStyle(str, Enum):
    """Execution style recommendation."""

    AGGRESSIVE = "aggressive"  # Cross spread, immediate
    PASSIVE = "passive"  # Rest in book, wait
    OPPORTUNISTIC = "opportunistic"  # Blend of both


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class QueueEstimate:
    """Queue position and fill time estimate for an order.

    Attributes:
        queue_position: Position in queue (front/middle/back).
        queue_size_ahead: Estimated volume ahead in queue.
        total_queue_size: Total queue size at this price level.
        estimated_fill_time_sec: Estimated time until fill.
        fill_probability: Probability of fill within time window.
        trade_rate: Observed trade rate at this level (volume/sec).
        fill_time_confidence: Confidence in fill time estimate (0–1).
        recommended_style: Execution style recommendation.
        timestamp: Estimate time.
    """

    queue_position: QueuePosition = QueuePosition.UNKNOWN
    queue_size_ahead: float = 0.0
    total_queue_size: float = 0.0
    estimated_fill_time_sec: Optional[float] = None
    fill_probability: FillProbability = FillProbability.MODERATE
    trade_rate: float = 0.0
    fill_time_confidence: float = 0.0
    recommended_style: ExecutionStyle = ExecutionStyle.PASSIVE
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def queue_progress(self) -> float:
        """Fraction through queue (0 = front, 1 = back)."""
        if self.total_queue_size == 0:
            return 0.0
        return self.queue_size_ahead / self.total_queue_size

    @property
    def is_fill_likely(self) -> bool:
        """Whether fill is probable."""
        return self.fill_probability in (
            FillProbability.VERY_HIGH,
            FillProbability.HIGH,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "queue_position": self.queue_position.value,
            "queue_size_ahead": round(self.queue_size_ahead, 2),
            "total_queue_size": round(self.total_queue_size, 2),
            "estimated_fill_time_sec": (
                round(self.estimated_fill_time_sec, 2)
                if self.estimated_fill_time_sec else None
            ),
            "fill_probability": self.fill_probability.value,
            "trade_rate": round(self.trade_rate, 4),
            "recommended_style": self.recommended_style.value,
        }


# ---------------------------------------------------------------------------
# QueuePositionEstimator
# ---------------------------------------------------------------------------


class QueuePositionEstimator:
    """Exchange queue position and fill time estimator.

    Predicts where an order sits in the limit order book queue
    and estimates expected fill time based on observed trade rate.
    Supports TWAP/VWAP execution optimization.

    Attributes:
        default_trade_rate: Fallback trade rate when no data available.
        confidence_decay: Decay factor for confidence with queue depth.
        history: Past queue estimates.
    """

    POSITION_THRESHOLDS: dict[QueuePosition, tuple[float, float]] = {
        QueuePosition.FRONT: (0.0, 0.10),
        QueuePosition.MIDDLE: (0.10, 0.70),
        QueuePosition.BACK: (0.70, 1.0),
    }

    PROBABILITY_THRESHOLDS: dict[FillProbability, tuple[float, float]] = {
        FillProbability.VERY_LOW: (0.0, 0.10),
        FillProbability.LOW: (0.10, 0.40),
        FillProbability.MODERATE: (0.40, 0.70),
        FillProbability.HIGH: (0.70, 0.90),
        FillProbability.VERY_HIGH: (0.90, 1.0),
    }

    def __init__(
        self,
        default_trade_rate: float = 100.0,  # 100 shares/sec default
    ) -> None:
        """Initialize the queue position estimator.

        Args:
            default_trade_rate: Default trade rate (volume/sec).
        """
        self.default_trade_rate = default_trade_rate
        self.history: list[QueueEstimate] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def estimate(
        self,
        queue_size: float,
        trade_rate: float,
        order_size: float = 0.0,
        position_in_queue: Optional[float] = None,
        time_horizon_sec: float = 60.0,
    ) -> QueueEstimate:
        """Estimate queue position and fill time.

        Args:
            queue_size: Total volume at this price level.
            trade_rate: Observed trade rate at this level (volume/sec).
            order_size: Size of the order being estimated.
            position_in_queue: Known position in queue (0=front, 1=back).
                               If None, estimate from order size.
            time_horizon_sec: Time window for fill probability.

        Returns:
            QueueEstimate with position, fill time, and recommendations.
        """
        if trade_rate <= 0:
            trade_rate = self.default_trade_rate

        # Estimate position in queue
        if position_in_queue is not None:
            queue_ahead = position_in_queue * queue_size
            progress = position_in_queue
        elif order_size > 0 and queue_size > 0:
            # Approximate: assume order is added at back
            queue_ahead = queue_size
            progress = 1.0
        else:
            queue_ahead = queue_size
            progress = 1.0

        # Classify position (inclusive upper bound for edge cases)
        position = QueuePosition.UNKNOWN
        for pos, (lo, hi) in self.POSITION_THRESHOLDS.items():
            if lo <= progress <= hi:
                position = pos
                break

        # Estimate fill time
        if trade_rate > 0:
            estimated_fill_time = queue_size / trade_rate if position_in_queue is not None else (queue_ahead / trade_rate)
        else:
            estimated_fill_time = None

        # Fill probability within time horizon
        if estimated_fill_time and trade_rate > 0:
            prob_fill = min(1.0, time_horizon_sec / max(estimated_fill_time, 0.001))
        else:
            prob_fill = 0.0

        # Classify probability (inclusive upper bound for edge cases)
        fill_prob = FillProbability.MODERATE
        for fp, (lo, hi) in self.PROBABILITY_THRESHOLDS.items():
            if lo <= prob_fill <= hi:
                fill_prob = fp
                break

        # Confidence: decays with queue depth (deeper = less certain)
        confidence = max(0.1, 1.0 - (queue_size / 100000.0))

        # Execution style recommendation
        style = self._recommend_style(
            position=position,
            fill_prob=fill_prob,
            estimated_fill_time=estimated_fill_time,
            time_horizon_sec=time_horizon_sec,
        )

        estimate = QueueEstimate(
            queue_position=position,
            queue_size_ahead=queue_ahead,
            total_queue_size=queue_size,
            estimated_fill_time_sec=estimated_fill_time,
            fill_probability=fill_prob,
            trade_rate=trade_rate,
            fill_time_confidence=confidence,
            recommended_style=style,
        )

        self.history.append(estimate)
        return estimate

    def estimate_from_snapshot(
        self,
        price: float,
        queue_volume: float,
        trade_rate: float,
        order_size: float = 0.0,
    ) -> QueueEstimate:
        """Estimate from order book snapshot data.

        Args:
            price: Order price level.
            queue_volume: Volume at this level.
            trade_rate: Observed trade rate.
            order_size: Order size being placed.

        Returns:
            QueueEstimate.
        """
        return self.estimate(
            queue_size=queue_volume,
            trade_rate=trade_rate,
            order_size=order_size,
        )

    # ------------------------------------------------------------------
    # Execution Style Recommendation
    # ------------------------------------------------------------------

    def _recommend_style(
        self,
        position: QueuePosition,
        fill_prob: FillProbability,
        estimated_fill_time: Optional[float],
        time_horizon_sec: float,
    ) -> ExecutionStyle:
        """Recommend execution style based on queue position.

        Args:
            position: Queue position.
            fill_prob: Fill probability.
            estimated_fill_time: Estimated fill time in seconds.
            time_horizon_sec: Execution time horizon.

        Returns:
            Recommended ExecutionStyle.
        """
        # At front with high fill prob → passive is fine
        if position == QueuePosition.FRONT and fill_prob in (
            FillProbability.VERY_HIGH, FillProbability.HIGH
        ):
            return ExecutionStyle.PASSIVE

        # At back or low fill prob → aggressive
        if position == QueuePosition.BACK or fill_prob in (
            FillProbability.LOW, FillProbability.VERY_LOW
        ):
            return ExecutionStyle.AGGRESSIVE

        # Middle → opportunistic
        if position == QueuePosition.MIDDLE:
            return ExecutionStyle.OPPORTUNISTIC

        # Time constraint: if fill unlikely within horizon, be aggressive
        if estimated_fill_time and estimated_fill_time > time_horizon_sec:
            return ExecutionStyle.AGGRESSIVE

        return ExecutionStyle.PASSIVE

    # ------------------------------------------------------------------
    # Multi-Level Analysis
    # ------------------------------------------------------------------

    def optimal_level(
        self,
        levels: list[dict[str, Any]],
        order_size: float,
        time_horizon_sec: float = 60.0,
        max_slippage_pct: float = 0.001,
    ) -> dict[str, Any]:
        """Find optimal price level for resting an order.

        Args:
            levels: List of level dicts with price, volume, trade_rate.
            order_size: Order size.
            time_horizon_sec: Desired fill time horizon.
            max_slippage_pct: Max acceptable price vs best.

        Returns:
            Dict with optimal level, estimates, and trade-offs.
        """
        if not levels:
            return {"optimal_price": None, "reason": "no_levels"}

        best_price = levels[0]["price"]

        candidates = []
        for level_dict in levels:
            price = level_dict["price"]
            queue = level_dict.get("volume", 0)
            rate = level_dict.get("trade_rate", self.default_trade_rate)

            slippage = abs(price - best_price) / max(best_price, 0.0001)
            if slippage > max_slippage_pct:
                continue

            est = self.estimate(
                queue_size=queue,
                trade_rate=rate,
                order_size=order_size,
                time_horizon_sec=time_horizon_sec,
            )

            candidates.append({
                "price": price,
                "queue_volume": queue,
                "fill_time": est.estimated_fill_time_sec,
                "fill_probability": est.fill_probability.value,
                "slippage": slippage,
                "score": (
                    (1.0 - slippage / max_slippage_pct) * 0.4 +
                    (est.fill_probability.fill_probability_value) * 0.6
                ),
            })

        if not candidates:
            return {"optimal_price": None, "reason": "no_eligible_levels"}

        best = max(candidates, key=lambda c: c["score"])
        return {
            "optimal_price": best["price"],
            "estimated_fill_time_sec": best["fill_time"],
            "fill_probability": best["fill_probability"],
            "slippage_pct": round(best["slippage"], 6),
            "candidates": candidates,
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_estimate(
        self,
        queue_size: float,
        trade_rate: float,
    ) -> dict[str, Any]:
        """Quick queue position estimate.

        Args:
            queue_size: Volume at the price level.
            trade_rate: Trade rate (volume/sec).

        Returns:
            Dict with estimated fill time and position.
        """
        est = self.estimate(queue_size=queue_size, trade_rate=trade_rate)
        return {
            "queue_position": est.queue_position.value,
            "estimated_fill_time_sec": (
                round(est.estimated_fill_time_sec, 2)
                if est.estimated_fill_time_sec else None
            ),
            "fill_probability": est.fill_probability.value,
            "recommended_style": est.recommended_style.value,
        }

    def last_result(self) -> Optional[QueueEstimate]:
        """Return the most recent queue estimate."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset estimation history."""
        self.history.clear()


# ---------------------------------------------------------------------------
# FillProbability.value property (numeric conversion)
# ---------------------------------------------------------------------------

def _fill_probability_value(self: FillProbability) -> float:
    """Numeric fill probability from classification."""
    values = {
        FillProbability.VERY_LOW: 0.05,
        FillProbability.LOW: 0.25,
        FillProbability.MODERATE: 0.55,
        FillProbability.HIGH: 0.80,
        FillProbability.VERY_HIGH: 0.95,
    }
    return values.get(self, 0.5)


FillProbability.fill_probability_value = property(_fill_probability_value)
