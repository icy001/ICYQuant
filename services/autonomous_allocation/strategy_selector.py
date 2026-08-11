"""Strategy Selector — selects which strategies should receive capital.

Based on allocation scores, capacity availability, and constraints,
determines the set of strategies to allocate to.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SelectionCriteria:
    """Criteria for strategy selection."""
    min_composite_score: float = 0.40
    min_survival_score: float = 0.60
    max_risk_score: float = 1.0
    min_liquidity_score: float = 0.15
    min_capacity_score: float = 0.20
    max_strategies: int = 10


@dataclass
class SelectStrategy:
    """A selected strategy ready for allocation."""
    strategy_id: str
    composite_score: float = 0.0
    alpha_score: float = 0.0
    risk_score: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    survival_score: float = 0.0
    rank: int = 0
    eligible: bool = True
    disqualification_reason: str = ""


@dataclass
class SelectionResult:
    """Result of strategy selection."""
    selected: List[SelectStrategy] = field(default_factory=list)
    rejected: List[SelectStrategy] = field(default_factory=list)
    total_eligible: int = 0
    total_candidates: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class StrategySelector:
    """Selects which strategies should receive capital allocation.

    Filters out strategies that fail minimum criteria:
    - Survival score below threshold → REJECT
    - Liquidity score below minimum → DEFER
    - Composite score below minimum → SKIP
    - Risk score too high → CAP
    """

    def __init__(self, criteria: Optional[SelectionCriteria] = None):
        self._criteria = criteria or SelectionCriteria()

    def select(self, strategies: Dict[str, Dict[str, float]],
               capacity_limits: Optional[Dict[str, float]] = None) -> SelectionResult:
        """Select eligible strategies for allocation."""
        result = SelectionResult()
        capacity_limits = capacity_limits or {}

        candidates = []
        for sid, scores in strategies.items():
            composite = scores.get("composite_score", 0.5)
            alpha = scores.get("alpha_score", 0.5)
            risk = scores.get("risk_score", 0.5)
            cap_score = scores.get("capacity_score", 0.5)
            liq_score = scores.get("liquidity_score", 0.5)
            surv_score = scores.get("survival_score", 0.5)

            strategy = SelectStrategy(
                strategy_id=sid,
                composite_score=composite,
                alpha_score=alpha,
                risk_score=risk,
                capacity_score=cap_score,
                liquidity_score=liq_score,
                survival_score=surv_score,
            )

            # Check disqualification criteria
            if surv_score < self._criteria.min_survival_score:
                strategy.eligible = False
                strategy.disqualification_reason = f"Survival {surv_score:.2f} < {self._criteria.min_survival_score:.2f}"
            elif liq_score < self._criteria.min_liquidity_score:
                strategy.eligible = False
                strategy.disqualification_reason = f"Liquidity {liq_score:.2f} < {self._criteria.min_liquidity_score:.2f}"
            elif cap_score < self._criteria.min_capacity_score:
                strategy.eligible = False
                strategy.disqualification_reason = f"Capacity {cap_score:.2f} < {self._criteria.min_capacity_score:.2f}"
            elif composite < self._criteria.min_composite_score:
                strategy.eligible = False
                strategy.disqualification_reason = f"Composite {composite:.2f} < {self._criteria.min_composite_score:.2f}"
            elif risk > self._criteria.max_risk_score:
                strategy.eligible = False
                strategy.disqualification_reason = f"Risk {risk:.2f} > {self._criteria.max_risk_score:.2f}"

            candidates.append(strategy)

        # Sort by composite score
        candidates.sort(key=lambda s: s.composite_score, reverse=True)

        # Assign ranks
        selected = []
        rejected = []
        rank = 0

        for s in candidates:
            if s.eligible and len(selected) < self._criteria.max_strategies:
                rank += 1
                s.rank = rank
                selected.append(s)
            else:
                if s.eligible and len(selected) >= self._criteria.max_strategies:
                    s.disqualification_reason = f"Max strategies ({self._criteria.max_strategies}) reached"
                rejected.append(s)

        result.selected = selected
        result.rejected = rejected
        result.total_eligible = len([s for s in candidates if s.eligible])
        result.total_candidates = len(candidates)
        return result
