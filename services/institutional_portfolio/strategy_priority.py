"""
Strategy Priority — Priority-Based Strategy Ordering

Assigns execution and capital priority scores to strategies.
Higher priority strategies get capital first, execute first, etc.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PriorityScore:
    strategy_id: str
    score: float = 50.0
    components: Dict[str, float] = field(default_factory=dict)


class StrategyPriority:
    """
    Computes priority scores for strategies in the portfolio.

    Components: expected_return, risk_adjusted_return, capital_efficiency,
    strategy_type_weight, manual_override, decay_urgency.

    Higher priority → capital allocated first, executed first.
    """

    def __init__(
        self,
        priority_id: Optional[str] = None,
        registry=None,
        efficiency=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.priority_id = priority_id or f"spri-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self._efficiency = efficiency
        self.config = config or {}
        self._weights = {
            "expected_return": 0.30,
            "risk_adjusted": 0.25,
            "capital_efficiency": 0.20,
            "decay_urgency": 0.10,
            "type_weight": 0.10,
            "manual": 0.05,
        }
        self._scores: Dict[str, PriorityScore] = {}

    def compute_all(self) -> Dict[str, PriorityScore]:
        if not self._registry:
            return {}
        self._scores.clear()
        for sid, rec in self._registry.get_active().items():
            self._scores[sid] = self._compute(sid, rec)
        return self._scores

    def _compute(self, strategy_id: str, record) -> PriorityScore:
        score = 0.0
        components = {}

        # Expected return component
        ret = getattr(record, 'expected_return', 0.05) * 100
        components["expected_return"] = min(1.0, ret / 0.20)

        # Risk-adjusted component
        sharpe = getattr(record, 'sharpe', 1.0)
        components["risk_adjusted"] = min(1.0, sharpe / 3.0)

        # Capital efficiency component
        if self._efficiency:
            eff = self._efficiency.get(strategy_id)
            components["capital_efficiency"] = eff.capital_efficiency if eff else 0.5
        else:
            components["capital_efficiency"] = 0.5

        # Type weight
        type_weights = {
            "ML": 0.9, "statistical_arbitrage": 0.85, "momentum": 0.8,
            "mean_reversion": 0.75, "trend": 0.7, "event": 0.65,
            "volatility": 0.5,
        }
        components["type_weight"] = type_weights.get(record.strategy_type, 0.5)

        # Decay urgency
        components["decay_urgency"] = 0.5

        # Manual
        components["manual"] = record.priority / 100.0

        for k, v in components.items():
            score += self._weights.get(k, 0.1) * v

        return PriorityScore(strategy_id=strategy_id, score=score, components=components)

    def get(self, strategy_id: str) -> Optional[PriorityScore]:
        return self._scores.get(strategy_id)

    def rank(self) -> List[Tuple[str, float]]:
        return sorted(
            [(sid, s.score) for sid, s in self._scores.items()],
            key=lambda x: -x[1],
        )

    def get_top_n(self, n: int = 5) -> List[Tuple[str, float]]:
        return self.rank()[:n]
