from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Candidate:
    """A candidate asset or strategy considered for selection."""

    name: str
    symbol: str = ""
    expected_return: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskAdjustedSelector:
    """Selects the best candidates considering risk-adjusted metrics.

    Not just return — considers volatility, drawdown, and exposure.
    """

    def __init__(
        self,
        risk_aversion: float = 1.0,
        min_sharpe: float = 0.0,
        max_volatility: float = float("inf"),
        max_drawdown_limit: float = 0.3,
    ):
        self.risk_aversion = risk_aversion
        self.min_sharpe = min_sharpe
        self.max_volatility = max_volatility
        self.max_drawdown_limit = max_drawdown_limit

    def select(
        self, candidates: List[Candidate]
    ) -> Candidate:
        """Select the best candidate by risk-adjusted score.

        Score = expected_return - risk_aversion * volatility
        """
        if not candidates:
            raise ValueError("No candidates provided")

        scored = self._score_candidates(candidates)
        return max(scored, key=lambda c: c.score)

    def _score_candidates(
        self, candidates: List[Candidate]
    ) -> List[Candidate]:
        """Score all candidates with risk adjustment."""
        for c in candidates:
            risk_penalty = self.risk_aversion * c.volatility
            c.score = round(c.expected_return - risk_penalty, 4)
        return candidates

    def select_top_n(
        self, candidates: List[Candidate], n: int = 3
    ) -> List[Candidate]:
        """Select top N risk-adjusted candidates."""
        filtered = self._filter_candidates(candidates)
        scored = self._score_candidates(filtered)
        ranked = sorted(scored, key=lambda c: c.score, reverse=True)
        return ranked[:n]

    def _filter_candidates(
        self, candidates: List[Candidate]
    ) -> List[Candidate]:
        """Filter candidates by risk constraints."""
        return [
            c
            for c in candidates
            if c.sharpe >= self.min_sharpe
            and c.volatility <= self.max_volatility
            and abs(c.max_drawdown) <= self.max_drawdown_limit
        ]

    def select_with_score(
        self, candidates: List[Candidate]
    ) -> Optional[Candidate]:
        """Select and return detailed scoring info as metadata."""
        filtered = self._filter_candidates(candidates)
        if not filtered:
            return None
        scored = self._score_candidates(filtered)
        selected = max(scored, key=lambda c: c.score)
        selected.metadata["risk_penalty"] = (
            self.risk_aversion * selected.volatility
        )
        selected.metadata["total_candidates"] = len(candidates)
        selected.metadata["passed_filter"] = len(filtered)
        return selected

    def select_by_sharpe(
        self, candidates: List[Candidate]
    ) -> Candidate:
        """Select by highest Sharpe ratio (classic approach)."""
        if not candidates:
            raise ValueError("No candidates provided")
        return max(candidates, key=lambda c: c.sharpe)
