"""
Signal Confidence Aggregator — Weighted Confidence Across Strategies

When multiple strategies agree on a signal direction, aggregate their
confidence into a composite score. Not 2 BUYS vs 1 SELL, but:

    Strategy A: BUY, conf=0.91
    Strategy B: BUY, conf=0.72
    Strategy C: SELL, conf=0.43
    → Aggregate: BUY, conf=0.82
"""

import uuid
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SignalConfidenceAggregator:
    """
    Aggregates signal confidence across multiple strategies.

    Uses Bayesian-inspired weighted confidence aggregation.
    More strategies agreeing → higher composite confidence.
    """

    def __init__(
        self,
        agg_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.agg_id = agg_id or f"sca-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._base_confidence = self.config.get("base_confidence", 0.5)

    def aggregate(self, signal_breakdown: Dict[str, float],
                  confidences: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Compute aggregate confidence for a signal direction.

        Args:
            signal_breakdown: {strategy_id: signal_value}
            confidences: {strategy_id: confidence_level}
        """
        confidences = confidences or {}

        buy_contributors = {k: v for k, v in signal_breakdown.items() if v > 0}
        sell_contributors = {k: v for k, v in signal_breakdown.items() if v < 0}

        buy_conf = self._aggregate_direction(buy_contributors, confidences)
        sell_conf = self._aggregate_direction(sell_contributors, confidences)

        # Determine net direction
        if buy_conf > sell_conf:
            direction = "BUY"
            net_confidence = buy_conf - sell_conf * 0.5
        elif sell_conf > buy_conf:
            direction = "SELL"
            net_confidence = sell_conf - buy_conf * 0.5
        else:
            direction = "HOLD"
            net_confidence = self._base_confidence

        net_confidence = max(0.0, min(1.0, net_confidence))

        return {
            "direction": direction,
            "confidence": net_confidence,
            "buy_confidence": buy_conf,
            "sell_confidence": sell_conf,
            "buy_count": len(buy_contributors),
            "sell_count": len(sell_contributors),
        }

    def _aggregate_direction(self, contributors: Dict[str, float],
                              confidences: Dict[str, float]) -> float:
        """Aggregate confidence for one direction (BUY or SELL)."""
        if not contributors:
            return 0.0

        # Weighted average of confidences, with bonus for multiple contributors
        total_weight = sum(abs(v) for v in contributors.values())
        if total_weight <= 0:
            return 0.0

        weighted_conf = sum(
            abs(v) * confidences.get(sid, self._base_confidence)
            for sid, v in contributors.items()
        ) / total_weight

        # Bonus for multiple independent confirmations
        diversity_bonus = min(0.15, (len(contributors) - 1) * 0.05)

        return min(1.0, weighted_conf + diversity_bonus)
