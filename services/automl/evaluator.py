"""Multi-Objective Model Evaluator.

Comprehensive evaluation across Sharpe, IC, Sortino, Drawdown,
Turnover, Win Rate, and Stability metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class EvaluationMetric(str, Enum):
    SHARPE = "sharpe"
    SORTINO = "sortino"
    ANNUAL_RETURN = "annual_return"
    MAX_DRAWDOWN = "max_drawdown"
    CALMAR = "calmar"
    WIN_RATE = "win_rate"
    TURNOVER = "turnover"
    IC_MEAN = "ic_mean"
    IC_IR = "ic_ir"
    RANK_IC = "rank_ic"
    STABILITY = "stability"
    COMPOSITE = "composite"


@dataclass
class ObjectiveConfig:
    """Configuration for multi-objective evaluation.

    Attributes:
        metrics: Which metrics to compute.
        weights: Weight for each metric in composite score.
        directions: "maximize" or "minimize" per metric.
        risk_free_rate: Annual risk-free rate for Sharpe/Sortino.
        periods_per_year: Periods per year (252 daily, 12 monthly).
        composite_method: "weighted_sum" or "pareto_rank".
    """

    metrics: List[EvaluationMetric] = field(default_factory=lambda: [
        EvaluationMetric.SHARPE,
        EvaluationMetric.SORTINO,
        EvaluationMetric.MAX_DRAWDOWN,
        EvaluationMetric.IC_MEAN,
        EvaluationMetric.STABILITY,
    ])
    weights: Dict[str, float] = field(default_factory=dict)
    directions: Dict[str, str] = field(default_factory=dict)
    risk_free_rate: float = 0.02
    periods_per_year: int = 252
    composite_method: str = "weighted_sum"


@dataclass
class EvaluationResult:
    """Result of multi-objective model evaluation."""

    metrics: Dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    passed: bool = True
    failures: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class MultiObjectiveEvaluator:
    """Evaluate models across multiple financial metrics.

    Supports individual metric computation and weighted composite scoring.
    """

    def __init__(self, config: Optional[ObjectiveConfig] = None) -> None:
        self.config = config or ObjectiveConfig()

    # ---- main evaluation ----

    def evaluate(
        self,
        returns: List[float],
        predictions: Optional[List[float]] = None,
        targets: Optional[List[float]] = None,
        signals: Optional[List[float]] = None,
    ) -> EvaluationResult:
        """Compute all configured metrics.

        Args:
            returns: Period returns (e.g. daily).
            predictions: Model predictions for IC computation.
            targets: Actual targets for IC computation.
            signals: Trading signals for turnover computation.

        Returns:
            EvaluationResult with all metrics.
        """
        result = EvaluationResult()

        for metric in self.config.metrics:
            try:
                value = self._compute_metric(metric, returns, predictions, targets, signals)
                result.metrics[metric.value] = value
            except Exception:
                result.metrics[metric.value] = float("nan")

        result.composite_score = self._compute_composite(result.metrics)
        return result

    def evaluate_batch(
        self,
        returns_batch: List[List[float]],
        predictions_batch: Optional[List[List[float]]] = None,
    ) -> List[EvaluationResult]:
        """Evaluate multiple return series."""
        results = []
        for i, rets in enumerate(returns_batch):
            preds = predictions_batch[i] if predictions_batch else None
            results.append(self.evaluate(rets, preds))
        return results

    # ---- individual metrics ----

    def sharpe_ratio(self, returns: List[float]) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 2:
            return 0.0
        excess = arr - self.config.risk_free_rate / self.config.periods_per_year
        mean = float(np.mean(excess))
        std = float(np.std(excess, ddof=0))
        if std == 0:
            return 0.0
        return float(mean / std * math.sqrt(self.config.periods_per_year))

    def sortino_ratio(self, returns: List[float]) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 2:
            return 0.0
        excess = arr - self.config.risk_free_rate / self.config.periods_per_year
        downside = excess[excess < 0]
        if len(downside) == 0:
            return float("inf")
        mean = float(np.mean(excess))
        std_down = float(np.std(downside, ddof=0))
        if std_down == 0:
            return 0.0
        return float(mean / std_down * math.sqrt(self.config.periods_per_year))

    def max_drawdown(self, returns: List[float]) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 2:
            return 0.0
        cumulative = np.cumprod(1 + arr)
        peak = np.maximum.accumulate(cumulative)
        dd = (cumulative - peak) / peak
        return float(abs(np.min(dd)))

    def annual_return(self, returns: List[float]) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return 0.0
        total = float(np.prod(1 + arr))
        n = len(arr)
        years = n / self.config.periods_per_year
        if years == 0:
            return 0.0
        return float(total ** (1 / years) - 1)

    def calmar_ratio(self, returns: List[float]) -> float:
        ann_ret = self.annual_return(returns)
        mdd = self.max_drawdown(returns)
        if mdd == 0:
            return float("inf") if ann_ret > 0 else float("-inf")
        return float(ann_ret / mdd)

    def win_rate(self, returns: List[float]) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return 0.0
        return float(np.mean(arr > 0))

    def turnover(self, signals: List[float]) -> float:
        """Average absolute change in signals (proxy for turnover)."""
        if len(signals) < 2:
            return 0.0
        changes = [abs(signals[i] - signals[i - 1]) for i in range(1, len(signals))]
        return float(np.mean(changes))

    def ic_mean(self, predictions: List[float], targets: List[float]) -> float:
        """Pearson correlation (Information Coefficient)."""
        pred = np.array(predictions, dtype=np.float64)
        targ = np.array(targets, dtype=np.float64)
        mask = ~np.isnan(pred) & ~np.isnan(targ)
        if mask.sum() < 3:
            return 0.0
        corr = np.corrcoef(pred[mask], targ[mask])
        return float(corr[0, 1])

    def ic_ir(self, predictions_list: List[List[float]], targets_list: List[List[float]]) -> float:
        """IC Information Ratio: mean(IC) / std(IC) across periods."""
        ics = []
        for pred, targ in zip(predictions_list, targets_list):
            ic = self.ic_mean(pred, targ)
            if not np.isnan(ic):
                ics.append(ic)
        if len(ics) < 2:
            return 0.0
        mean_ic = float(np.mean(ics))
        std_ic = float(np.std(ics, ddof=1))
        if std_ic == 0:
            return 0.0
        return float(mean_ic / std_ic)

    def rank_ic(self, predictions: List[float], targets: List[float]) -> float:
        """Spearman (Rank IC)."""
        from scipy.stats import spearmanr
        pred = np.array(predictions, dtype=np.float64)
        targ = np.array(targets, dtype=np.float64)
        mask = ~np.isnan(pred) & ~np.isnan(targ)
        if mask.sum() < 3:
            return 0.0
        corr, _ = spearmanr(pred[mask], targ[mask])
        return float(corr)

    def stability(self, returns: List[float]) -> float:
        """Rolling Sharpe stability: 1 - std(rolling_sharpe)/mean(rolling_sharpe)."""
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        window = max(21, len(arr) // 4)
        if len(arr) < window * 2:
            return 0.0

        rolling_sharpes = []
        for i in range(0, len(arr) - window, window):
            chunk = arr[i : i + window]
            rolling_sharpes.append(self.sharpe_ratio(chunk.tolist()))

        if len(rolling_sharpes) < 2:
            return 0.0
        mean_s = float(np.mean(rolling_sharpes))
        std_s = float(np.std(rolling_sharpes, ddof=1))
        if abs(mean_s) < 1e-10:
            return 0.0
        return float(max(0.0, 1.0 - std_s / abs(mean_s)))

    # ---- composite ----

    def _compute_composite(self, metrics: Dict[str, float]) -> float:
        """Compute weighted composite score."""
        if self.config.composite_method == "weighted_sum":
            return self._weighted_sum(metrics)
        return self._weighted_sum(metrics)

    def _weighted_sum(self, metrics: Dict[str, float]) -> float:
        weights = self.config.weights
        directions = self.config.directions
        if not weights:
            # Equal weight on configured metrics
            n = max(len(self.config.metrics), 1)
            weights = {m.value: 1.0 / n for m in self.config.metrics}

        # Default directions
        maximize_default = {EvaluationMetric.MAX_DRAWDOWN.value, EvaluationMetric.TURNOVER.value}

        score = 0.0
        total_weight = 0.0
        for key, value in metrics.items():
            if key in weights and not np.isnan(value):
                w = weights[key]
                direction = directions.get(key, "minimize" if key in maximize_default else "maximize")
                # Normalize: for minimize metrics, negate so higher is always better
                if direction == "minimize":
                    value = -value
                score += w * value
                total_weight += w

        return score / total_weight if total_weight > 0 else 0.0

    # ---- internal ----

    def _compute_metric(
        self,
        metric: EvaluationMetric,
        returns: List[float],
        predictions: Optional[List[float]],
        targets: Optional[List[float]],
        signals: Optional[List[float]],
    ) -> float:
        if metric == EvaluationMetric.SHARPE:
            return self.sharpe_ratio(returns)
        elif metric == EvaluationMetric.SORTINO:
            return self.sortino_ratio(returns)
        elif metric == EvaluationMetric.MAX_DRAWDOWN:
            return self.max_drawdown(returns)
        elif metric == EvaluationMetric.ANNUAL_RETURN:
            return self.annual_return(returns)
        elif metric == EvaluationMetric.CALMAR:
            return self.calmar_ratio(returns)
        elif metric == EvaluationMetric.WIN_RATE:
            return self.win_rate(returns)
        elif metric == EvaluationMetric.TURNOVER:
            return self.turnover(signals or [])
        elif metric == EvaluationMetric.IC_MEAN:
            return self.ic_mean(predictions or [], targets or [])
        elif metric == EvaluationMetric.RANK_IC:
            return self.rank_ic(predictions or [], targets or [])
        elif metric == EvaluationMetric.STABILITY:
            return self.stability(returns)
        else:
            return float("nan")
