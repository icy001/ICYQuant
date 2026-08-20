"""Robustness checks for Discovery Lab v1.

Two checks protect against overfitting:

1. **Parameter stability** — a candidate is not allowed to depend on a magic
   parameter point.  Its "neighbourhood" is every other candidate sharing the
   same structure on the same asset.  A neighbourhood is stable when a large
   fraction of neighbours have a positive OOS Sharpe and the dispersion of
   neighbour Sharpe values is small (low coefficient of variation).  The user's
   canonical overfitting pattern — one "magic" parameter point (Sharpe 2.87)
   surrounded by much weaker neighbours (0.82 / 0.91 / 0.74) — is caught by
   a low neighbour positive fraction or, when the lone spike inflates the
   dispersion, by the CV requirement.

2. **Walk-forward** — the candidate is run over rolling in-sample/out-of-sample
   windows *inside Train + Validation only* (the final OOS segment is never
   touched).  v1 keeps the candidate's parameters fixed across windows, so this
   is a regime-stability test rather than a re-optimisation loop.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from .backtest import BacktestResult
from .split import WalkForwardWindow, TimeSplit, build_walk_forward_windows


@dataclass
class StabilityReport:
    """Parameter-stability result for one (candidate, asset) pair."""

    candidate_id: str
    structure_id: str
    asset: str
    neighbor_count: int = 0
    neighbor_positive_frac: float = 0.0
    neighbor_mean_sharpe: float = 0.0
    neighbor_std_sharpe: float = 0.0
    cv: float = 0.0
    min_positive_frac: float = 0.5
    max_cv: float = 1.5
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "structure_id": self.structure_id,
            "asset": self.asset,
            "neighbor_count": self.neighbor_count,
            "neighbor_positive_frac": round(self.neighbor_positive_frac, 4),
            "neighbor_mean_sharpe": round(self.neighbor_mean_sharpe, 4),
            "neighbor_std_sharpe": round(self.neighbor_std_sharpe, 4),
            "cv": round(self.cv, 4),
            "passed": self.passed,
        }


@dataclass
class WalkForwardReport:
    """Walk-forward result for one (candidate, asset) pair."""

    candidate_id: str
    asset: str
    windows_total: int = 0
    windows_positive: int = 0
    oos_sharpes: list[float] = field(default_factory=list)
    oos_returns: list[float] = field(default_factory=list)
    min_positive_frac: float = 0.66
    passed: bool = False

    @property
    def positive_frac(self) -> float:
        if self.windows_total == 0:
            return 0.0
        return self.windows_positive / self.windows_total

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "asset": self.asset,
            "windows_total": self.windows_total,
            "windows_positive": self.windows_positive,
            "positive_frac": round(self.positive_frac, 4),
            "oos_sharpes": [round(s, 4) for s in self.oos_sharpes],
            "oos_returns": [round(r, 6) for r in self.oos_returns],
            "passed": self.passed,
        }


def parameter_stability(
    candidate_id: str,
    structure_id: str,
    asset: str,
    neighbor_oos_sharpes: list[float],
    min_positive_frac: float = 0.5,
    max_cv: float = 1.5,
) -> StabilityReport:
    """Evaluate parameter stability from same-structure neighbours.

    ``neighbor_oos_sharpes`` are the OOS Sharpes of every other candidate that
    shares ``structure_id`` on ``asset`` (only neighbours that completed an OOS
    backtest count).  Pass requires:

        positive_frac(neighbours) >= min_positive_frac
        AND cv(oos_sharpes) <= max_cv

    A candidate with zero neighbours reports ``passed=False`` (unknown -> fail
    closed, consistent with the Gate's fail-closed philosophy).
    """
    vals = [s for s in neighbor_oos_sharpes]
    report = StabilityReport(
        candidate_id=candidate_id,
        structure_id=structure_id,
        asset=asset,
        neighbor_count=len(vals),
        min_positive_frac=min_positive_frac,
        max_cv=max_cv,
    )
    if not vals:
        return report

    positive = sum(1 for s in vals if s > 0)
    report.neighbor_positive_frac = positive / len(vals)
    report.neighbor_mean_sharpe = sum(vals) / len(vals)
    if len(vals) >= 2:
        var = sum((s - report.neighbor_mean_sharpe) ** 2 for s in vals) / (len(vals) - 1)
        report.neighbor_std_sharpe = math.sqrt(var)
    if report.neighbor_mean_sharpe != 0:
        report.cv = report.neighbor_std_sharpe / abs(report.neighbor_mean_sharpe)

    report.passed = (
        report.neighbor_positive_frac >= min_positive_frac
        and report.cv <= max_cv
    )
    return report


def walk_forward_check(
    candidate_id: str,
    asset: str,
    window_results: list[BacktestResult],
    min_positive_frac: float = 0.66,
) -> WalkForwardReport:
    """Evaluate walk-forward from per-window OOS backtest results.

    A window counts as positive when its OOS segment has a positive total
    return (net of costs).  Pass requires ``positive/windows >= min_positive_frac``.
    """
    report = WalkForwardReport(
        candidate_id=candidate_id,
        asset=asset,
        windows_total=len(window_results),
        min_positive_frac=min_positive_frac,
    )
    for r in window_results:
        report.oos_sharpes.append(r.metrics.sharpe)
        report.oos_returns.append(r.metrics.total_return)
        if r.metrics.total_return > 0:
            report.windows_positive += 1
    report.passed = (
        report.windows_total > 0
        and report.positive_frac >= min_positive_frac
    )
    return report


def build_windows(split: TimeSplit, **kwargs) -> list[WalkForwardWindow]:
    """Convenience wrapper (see :func:`build_walk_forward_windows`)."""
    return build_walk_forward_windows(split, **kwargs)
