"""Strategy Ranker — ranks strategies for capital allocation priority.

Pipeline: Alpha → Risk → Capacity → Liquidity → Impact → Stress → Survival → Score → Rank
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StrategyRank:
    """Ranking result for a single strategy."""
    strategy_id: str
    rank: int = 0
    composite_score: float = 0.0
    alpha_score: float = 0.0
    risk_score: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    impact_score: float = 0.0
    stress_score: float = 0.0
    survival_score: float = 0.0
    rank_change: int = 0  # change from previous rank
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RankBoard:
    """Complete strategy ranking board."""
    ranks: List[StrategyRank] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_strategies: int = 0

    def top_n(self, n: int = 3) -> List[StrategyRank]:
        return self.ranks[:n]

    def bottom_n(self, n: int = 3) -> List[StrategyRank]:
        return self.ranks[-n:] if n <= len(self.ranks) else list(reversed(self.ranks))


class StrategyRanker:
    """Real-time strategy ranking for capital allocation.

    Ranks strategies by composite allocation score and tracks
    rank changes for rotation decisions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._alpha_weight = self._config.get("alpha_weight", 0.25)
        self._risk_weight = self._config.get("risk_weight", 0.15)
        self._capacity_weight = self._config.get("capacity_weight", 0.15)
        self._liquidity_weight = self._config.get("liquidity_weight", 0.12)
        self._impact_weight = self._config.get("impact_weight", 0.10)
        self._stress_weight = self._config.get("stress_weight", 0.12)
        self._survival_weight = self._config.get("survival_weight", 0.11)
        self._previous_ranks: Dict[str, int] = {}

    def compute_composite_score(self, alpha: float, risk: float,
                                 capacity: float, liquidity: float,
                                 impact: float, stress: float,
                                 survival: float) -> float:
        """Compute composite allocation score."""
        return (
            self._alpha_weight * alpha +
            self._risk_weight * risk +
            self._capacity_weight * capacity +
            self._liquidity_weight * liquidity +
            self._impact_weight * impact +
            self._stress_weight * stress +
            self._survival_weight * survival
        )

    def rank(self, strategies: Dict[str, Dict[str, float]]) -> RankBoard:
        """Rank strategies by composite allocation score."""
        scored = []
        for sid, scores in strategies.items():
            alpha = scores.get("alpha_score", 0.5)
            risk = scores.get("risk_score", 0.5)
            capacity = scores.get("capacity_score", 0.5)
            liquidity = scores.get("liquidity_score", 0.5)
            impact = scores.get("impact_score", 0.5)
            stress = scores.get("stress_score", 0.5)
            survival = scores.get("survival_score", 0.5)

            composite = self.compute_composite_score(
                alpha, risk, capacity, liquidity, impact, stress, survival
            )

            scored.append((sid, composite, alpha, risk, capacity,
                          liquidity, impact, stress, survival))

        # Sort by composite score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        ranks = []
        for i, (sid, composite, alpha, risk, capacity,
                liquidity, impact, stress, survival) in enumerate(scored):
            prev_rank = self._previous_ranks.get(sid, i + 1)
            rank_change = prev_rank - (i + 1)  # positive = improvement

            ranks.append(StrategyRank(
                strategy_id=sid,
                rank=i + 1,
                composite_score=composite,
                alpha_score=alpha,
                risk_score=risk,
                capacity_score=capacity,
                liquidity_score=liquidity,
                impact_score=impact,
                stress_score=stress,
                survival_score=survival,
                rank_change=rank_change,
            ))

        # Save for next comparison
        self._previous_ranks = {r.strategy_id: r.rank for r in ranks}

        return RankBoard(ranks=ranks, total_strategies=len(ranks))

    def get_top(self, strategies: Dict[str, Dict[str, float]],
                n: int = 3) -> List[StrategyRank]:
        """Get top N strategies."""
        board = self.rank(strategies)
        return board.top_n(n)

    def get_rank_changes(self) -> Dict[str, int]:
        """Get which strategies improved or declined in rank."""
        return {
            sid: self._previous_ranks.get(sid, 0) - rank
            for sid, rank in self._previous_ranks.items()
        }
