from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StrategyScore:
    """A strategy with its evaluation metrics for ranking."""

    name: str
    sharpe: float = 0.0
    returns: float = 0.0
    max_drawdown: float = 0.0
    ic: float = 0.0
    score: float = 0.0
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyRankingEngine:
    """Ranks multiple trading strategies by various metrics."""

    def __init__(
        self,
        metric: str = "sharpe",
        sharpe_weight: float = 0.4,
        returns_weight: float = 0.2,
        drawdown_weight: float = 0.2,
        ic_weight: float = 0.2,
    ):
        self.metric = metric
        self.sharpe_weight = sharpe_weight
        self.returns_weight = returns_weight
        self.drawdown_weight = drawdown_weight
        self.ic_weight = ic_weight

    def rank(self, strategies: List[StrategyScore]) -> List[StrategyScore]:
        """Rank strategies by their score in descending order.

        Returns a new sorted list with rank numbers assigned.
        """
        ranked = sorted(strategies, key=lambda s: s.score, reverse=True)
        for i, s in enumerate(ranked):
            s.rank = i + 1
        return ranked

    def rank_metrics(self, scores: List[float]) -> List[float]:
        """Simple numeric ranking.

        Args:
            scores: List of raw numeric scores.

        Returns:
            Sorted list in descending order.
        """
        return sorted(scores, reverse=True)

    def compute_composite_score(self, strategy: StrategyScore) -> float:
        """Compute a weighted composite score from strategy metrics."""
        # Normalize drawdown (invert so lower drawdown = higher score)
        drawdown_score = max(0.0, 1.0 - abs(strategy.max_drawdown))
        return round(
            self.sharpe_weight * strategy.sharpe
            + self.returns_weight * strategy.returns
            + self.drawdown_weight * drawdown_score
            + self.ic_weight * strategy.ic,
            4,
        )

    def rank_by_composite(
        self, strategies: List[StrategyScore]
    ) -> List[StrategyScore]:
        """Rank using composite score computation."""
        for s in strategies:
            s.score = self.compute_composite_score(s)
        return self.rank(strategies)

    def top_n(
        self, strategies: List[StrategyScore], n: int = 3
    ) -> List[StrategyScore]:
        """Return the top N ranked strategies."""
        ranked = self.rank_by_composite(strategies)
        return ranked[:n]

    def rank_by_metric(
        self, strategies: List[StrategyScore], metric: str
    ) -> List[StrategyScore]:
        """Rank by a specific metric."""
        metric_map = {
            "sharpe": lambda s: s.sharpe,
            "returns": lambda s: s.returns,
            "drawdown": lambda s: -abs(s.max_drawdown),
            "ic": lambda s: s.ic,
        }
        key_fn = metric_map.get(metric, lambda s: s.score)
        ranked = sorted(strategies, key=key_fn, reverse=True)
        for i, s in enumerate(ranked):
            s.rank = i + 1
        return ranked
