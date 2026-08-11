"""Strategy Weight — dynamic strategy weight computation.

Strategy weights are no longer fixed. They adjust based on:
- Alpha changes
- Risk changes
- Capacity changes
- Market conditions

All weight changes must pass constraint validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DynamicWeight:
    """Dynamically computed weight for a strategy."""
    strategy_id: str
    weight: float = 0.0
    previous_weight: float = 0.0
    weight_change: float = 0.0
    alpha_driver: float = 0.0
    risk_driver: float = 0.0
    capacity_driver: float = 0.0
    liquidity_driver: float = 0.0
    constrained: bool = False
    constraint_reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WeightAllocation:
    """Complete weight allocation across strategies."""
    weights: Dict[str, DynamicWeight] = field(default_factory=dict)
    total_weight: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = ["Strategy Weights:"]
        for sid, w in self.weights.items():
            change_str = f"{w.weight_change:+.4f}" if w.weight_change != 0 else "0"
            cnstr = " [CONSTRAINED]" if w.constrained else ""
            lines.append(f"  {sid}: {w.previous_weight:.4f} → {w.weight:.4f} ({change_str}){cnstr}")
        return "\n".join(lines)


class StrategyWeight:
    """Computes dynamic strategy weights based on allocation scores.

    Weight ∝ composite_score, subject to constraints:
    - Max single strategy weight
    - Min weight
    - Survival threshold
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._max_single_weight = self._config.get("max_single_weight", 0.40)
        self._min_single_weight = self._config.get("min_single_weight", 0.02)
        self._previous_weights: Dict[str, float] = {}

    def compute_weights(self, strategies: Dict[str, Dict[str, float]],
                        constraints: Optional[Dict[str, Any]] = None) -> WeightAllocation:
        """Compute dynamic weights based on composite scores.

        Weight_i = score_i / Σ scores_j, then apply constraints.
        """
        if not strategies:
            return WeightAllocation()

        # Compute raw weights proportional to composite score
        total_score = sum(s.get("composite_score", 0.5) for s in strategies.values())
        if total_score <= 0:
            total_score = 1.0

        raw_weights = {}
        for sid, scores in strategies.items():
            raw_weights[sid] = scores.get("composite_score", 0.5) / total_score

        # Apply constraints
        weights = {}
        for sid, raw_weight in raw_weights.items():
            prev = self._previous_weights.get(sid, raw_weight)

            # Compute drivers
            scores = strategies.get(sid, {})
            alpha = scores.get("alpha_score", 0.5)
            risk = scores.get("risk_score", 0.5)
            capacity = scores.get("capacity_score", 0.5)
            liquidity = scores.get("liquidity_score", 0.5)

            weight = raw_weight
            constrained = False
            reason = ""

            # Cap at max
            if weight > self._max_single_weight:
                weight = self._max_single_weight
                constrained = True
                reason = f"Capped at max {self._max_single_weight:.2%}"

            # Floor at min (if non-zero)
            if weight > 0 and weight < self._min_single_weight:
                weight = 0.0  # Too small → zero
                constrained = True
                reason = f"Below min {self._min_single_weight:.2%}, set to 0"

            weights[sid] = DynamicWeight(
                strategy_id=sid,
                weight=weight,
                previous_weight=prev,
                weight_change=weight - prev,
                alpha_driver=alpha,
                risk_driver=risk,
                capacity_driver=capacity,
                liquidity_driver=liquidity,
                constrained=constrained,
                constraint_reason=reason,
            )

        # Renormalize
        total = sum(w.weight for w in weights.values())
        if total > 0 and abs(total - 1.0) > 0.001:
            for sid in weights:
                weights[sid].weight /= total

        # Save for next comparison
        self._previous_weights = {sid: w.weight for sid, w in weights.items()}

        return WeightAllocation(
            weights=weights,
            total_weight=sum(w.weight for w in weights.values()),
        )

    def get_weight_changes(self) -> Dict[str, float]:
        """Get which strategies increased/decreased in weight."""
        return self._previous_weights
