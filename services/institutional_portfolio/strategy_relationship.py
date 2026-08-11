"""
Strategy Relationship — Pairwise Strategy Relationship Analysis

Analyzes relationships between strategy pairs: correlation, co-integration,
lead-lag, signal overlap, and capital competition.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyPairRelation:
    strategy_a: str
    strategy_b: str
    correlation: float = 0.0
    co_integration: float = 0.0
    signal_overlap: float = 0.0
    capital_competition: float = 0.0
    relationship_type: str = "INDEPENDENT"


class StrategyRelationship:
    """
    Analyzes pairwise strategy relationships for portfolio construction.

    Knows which strategies tend to move together, compete for capital,
    overlap in signals, or have predictive relationships.
    """

    def __init__(
        self,
        rel_id: Optional[str] = None,
        registry=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.rel_id = rel_id or f"srel-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self.config = config or {}
        self._relations: Dict[Tuple[str, str], StrategyPairRelation] = {}

    def set(
        self,
        s1: str, s2: str,
        correlation: float = 0.0,
        signal_overlap: float = 0.0,
        capital_competition: float = 0.0,
    ) -> StrategyPairRelation:
        key = tuple(sorted([s1, s2]))
        relation = StrategyPairRelation(
            strategy_a=key[0],
            strategy_b=key[1],
            correlation=correlation,
            signal_overlap=signal_overlap,
            capital_competition=capital_competition,
            relationship_type=(
                "HIGHLY_CORRELATED" if abs(correlation) > 0.7 else
                "MODERATELY_CORRELATED" if abs(correlation) > 0.4 else
                "INDEPENDENT"
            ),
        )
        self._relations[key] = relation
        return relation

    def get(self, s1: str, s2: str) -> Optional[StrategyPairRelation]:
        return self._relations.get(tuple(sorted([s1, s2])))

    def get_all_for_strategy(self, strategy_id: str) -> Dict[str, StrategyPairRelation]:
        result = {}
        for (a, b), rel in self._relations.items():
            if a == strategy_id:
                result[b] = rel
            elif b == strategy_id:
                result[a] = rel
        return result

    def get_competing_strategies(self, strategy_id: str) -> List[str]:
        return [
            other for (a, b), rel in self._relations.items()
            if (a == strategy_id or b == strategy_id) and rel.capital_competition > 0.5
            for other in ([b] if a == strategy_id else [a])
        ]
