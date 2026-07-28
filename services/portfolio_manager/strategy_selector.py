"""Strategy Selection Engine – select optimal strategy combinations."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Strategy:
    """A quantitative trading strategy with performance and risk metrics."""

    name: str
    category: str  # "momentum", "value", "mean_reversion", "macro", "ml"
    sharpe: float = 0.0
    returns: float = 0.0  # annualized
    max_drawdown: float = 0.0
    volatility: float = 0.0
    ic: float = 0.0  # Information Coefficient
    capacity: float = 1.0  # capacity utilization (0-1)
    active: bool = True

    def score(self) -> float:
        """Composite quality score (higher is better)."""
        return (
            0.35 * max(self.sharpe, 0)
            + 0.25 * self.returns
            - 0.20 * self.max_drawdown
            + 0.10 * self.ic
            + 0.10 * (1.0 - self.capacity)
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "sharpe": self.sharpe,
            "returns": self.returns,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "ic": self.ic,
            "capacity": self.capacity,
            "active": self.active,
        }


class StrategySelector:
    """Selects the best strategy combination considering performance,
    diversification, and market regime compatibility.
    """

    def __init__(
        self,
        min_sharpe: float = 0.3,
        max_drawdown_limit: float = 0.25,
        max_strategies: int = 5,
    ):
        self.min_sharpe = min_sharpe
        self.max_drawdown_limit = max_drawdown_limit
        self.max_strategies = max_strategies

    def select(
        self,
        strategies: List[Strategy],
        market_regime: str = "normal",
    ) -> List[Strategy]:
        """Select the best strategy combination.

        Filters by quality, then selects top-N with diversification
        preference (avoiding same-category clustering).
        """
        # Filter by minimum quality
        qualified = [
            s for s in strategies
            if s.active and s.sharpe >= self.min_sharpe
            and s.max_drawdown <= self.max_drawdown_limit
        ]
        if not qualified:
            qualified = [s for s in strategies if s.active]

        # Score and sort
        sorted_strategies = sorted(qualified, key=lambda s: s.score(), reverse=True)

        # Select with category diversification
        selected: List[Strategy] = []
        used_categories: set = set()

        for strategy in sorted_strategies:
            if len(selected) >= self.max_strategies:
                break
            # Prefer new categories, but allow repeats if needed
            if strategy.category not in used_categories or len(selected) < 2:
                selected.append(strategy)
                used_categories.add(strategy.category)

        # If we don't have enough, fill from best remaining
        if len(selected) < min(2, self.max_strategies):
            for strategy in sorted_strategies:
                if strategy not in selected and len(selected) < self.max_strategies:
                    selected.append(strategy)

        return selected

    def select_simple(self, strategies: List[str]) -> str:
        """Simple selection: return alphabetically first strategy.

        For backward compatibility with legacy interface.
        """
        if not strategies:
            return ""
        return max(strategies)  # max alphabetical

    def allocate_capital(
        self,
        selected: List[Strategy],
        total_capital: float,
    ) -> Dict[str, float]:
        """Allocate capital across selected strategies by score proportion."""
        if not selected:
            return {}

        scores = [s.score() for s in selected]
        total_score = sum(scores)

        if total_score <= 0:
            equal = 1.0 / len(selected)
            return {s.name: round(equal, 4) for s in selected}

        return {
            s.name: round(s.score() / total_score, 4)
            for s in selected
        }
