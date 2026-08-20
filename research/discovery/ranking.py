"""Multi-factor ranking for Discovery Lab v1.

Score components follow the sealed weights in ``spec.RANKING_WEIGHTS``.
Every component is rank-normalised across the *surviving* candidates
(0 = worst, 1 = best), which makes the score scale-free and robust to outliers.

**Hard rule**: a candidate that fails OOS (``oos_sharpe < min_oos_sharpe`` or
``oos_return < min_oos_return``) is rejected outright — no score can "rescue"
an OOS failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .spec import SCORE_WEIGHTS


@dataclass
class DiscoveryScore:
    """One candidate's ranked score across all assets that passed the gate."""

    candidate_id: str
    family: str
    structure_id: str
    params: dict[str, Any]
    assets_passed: list[str]
    total_score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)
    oos_sharpe: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "family": self.family,
            "structure_id": self.structure_id,
            "params": self.params,
            "assets_passed": self.assets_passed,
            "total_score": round(self.total_score, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "raw": {k: round(v, 6) for k, v in self.raw.items()},
        }


def _rank_normalise(values: list[float]) -> list[float]:
    """Rank-based normalisation to [0, 1] (best = 1)."""
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    for rank_pos, idx in enumerate(order):
        ranks[idx] = rank_pos / (n - 1) if n > 1 else 1.0
    return ranks


def rank_candidates(
    scores_in: list[DiscoveryScore],
    weights: Optional[dict[str, float]] = None,
) -> list[DiscoveryScore]:
    """Compute total scores and return the list sorted best-first.

    ``scores_in`` must already exclude OOS failures (the engine enforces the
    OOS hard rule before calling this).  If any OOS failure slips through here
    it is dropped.
    """
    weights = weights or SCORE_WEIGHTS
    # drop OOS failures as a hard rule (defence in depth)
    survivors = [
        s for s in scores_in
        if s.raw.get("oos_sharpe", 0.0) >= weights.get("min_oos_sharpe", 0.8)
        and s.raw.get("oos_return", -1.0) >= weights.get("min_oos_return", 0.0)
    ]
    if not survivors:
        return []

    # rank-normalise each component across survivors
    def _norm(comp: str, invert: bool = False) -> list[float]:
        vals = [s.raw.get(comp, getattr(s, comp, 0.0)) for s in survivors]
        norm = _rank_normalise(vals)
        if invert:
            norm = [1.0 - v for v in norm]
        return norm

    comps = {
        "oos_sharpe": _norm("oos_sharpe"),
        "oos_return": _norm("oos_return"),
        "drawdown": _norm("max_drawdown", invert=True),
        "profit_factor": _norm("profit_factor"),
        "stability": _norm("stability"),
        "trade_count": _norm("trade_count"),
        "complexity": _norm("complexity", invert=True),
    }

    for i, s in enumerate(survivors):
        s.components = {c: comps[c][i] for c in comps}
        s.total_score = sum(
            weights[c] * s.components[c] for c in comps if c in weights
        )
        s.assets_passed = list(s.assets_passed)

    survivors.sort(key=lambda s: s.total_score, reverse=True)
    return survivors


def build_score(
    candidate_id: str,
    family: str,
    structure_id: str,
    params: dict[str, Any],
    assets_passed: list[str],
    oos_sharpe: float,
    oos_return: float,
    max_drawdown: float,
    profit_factor: float,
    stability: float,
    trade_count: int,
    n_indicators: int,
    n_params: int,
) -> DiscoveryScore:
    """Aggregate a (candidate, best-asset) snapshot into a DiscoveryScore.

    Values are aggregated over the assets that passed the gate (mean of the
    per-asset values).  ``stability`` is the mean neighbour-positive fraction
    across passed assets; ``complexity`` is derived from the structure size.
    """
    score = DiscoveryScore(
        candidate_id=candidate_id,
        family=family,
        structure_id=structure_id,
        params=dict(params),
        assets_passed=assets_passed,
        raw={
            "oos_sharpe": oos_sharpe,
            "oos_return": oos_return,
            "max_drawdown": max_drawdown,
            "profit_factor": profit_factor,
            "stability": stability,
            "trade_count": float(trade_count),
            "complexity": float(n_indicators + n_params),
        },
    )
    score.oos_sharpe = oos_sharpe
    return score
