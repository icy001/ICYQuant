"""
ICYQuant Cross Validator - Time-series cross-validation for quant finance.

Unlike standard random K-fold, quant ML requires time-aware validation:

    Train ────────► Test

    Train ─────────────► Test

    Train ───────────────────► Test

Each fold respects chronological ordering to prevent future information leakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CVMethod(Enum):
    """Cross-validation methods."""

    PURGED_KFOLD = "purged_kfold"       # time-aware k-fold with purge gap
    WALK_FORWARD = "walk_forward"       # rolling walk-forward
    EXPANDING_WINDOW = "expanding"      # expanding training window
    COMBINATORIAL_PURGED = "combinatorial_purged"  # combinatorial purged CV


@dataclass
class CVConfig:
    """Cross-validation configuration."""

    method: CVMethod = CVMethod.PURGED_KFOLD
    n_splits: int = 5

    # Purged CV
    purge_days: int = 5          # gap between train/test
    embargo_days: int = 0         # embargo after test start
    min_train_days: int = 252    # minimum training window

    # Walk-forward
    train_window_days: int = 504
    test_window_days: int = 63
    step_size_days: int = 63

    # Metrics
    primary_metric: str = "ic"
    metrics: List[str] = field(default_factory=lambda: ["ic", "rank_ic", "rmse", "sharpe"])


@dataclass
class CVFold:
    """A single cross-validation fold."""

    fold_id: int = 0
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None
    train_count: int = 0
    test_count: int = 0


@dataclass
class CVResult:
    """Cross-validation results."""

    cv_id: str = ""
    method: CVMethod = CVMethod.PURGED_KFOLD
    n_splits: int = 0

    # Per-fold metrics
    fold_metrics: List[Dict[str, float]] = field(default_factory=list)

    # Aggregate metrics
    metrics_mean: Dict[str, float] = field(default_factory=dict)
    metrics_std: Dict[str, float] = field(default_factory=dict)

    # Per-fold details
    folds: List[CVFold] = field(default_factory=list)

    # Metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_time_seconds: float = 0.0

    @property
    def primary_score(self) -> float:
        return self.metrics_mean.get("ic", 0.0)

    @property
    def score_stability(self) -> float:
        """Score stability = 1 - (std/mean) for primary metric."""
        mean = self.metrics_mean.get("ic", 0.0)
        std = self.metrics_std.get("ic", 0.0)
        if abs(mean) < 1e-8:
            return 0.0
        return 1.0 - min(std / abs(mean), 1.0)


class CrossValidator:
    """Time-series cross-validation for quant finance models.

    Key principles:
    1. Never shuffle time-series data
    2. Always train on past, test on future
    3. Include purge gaps between train and test
    4. Report metric stability across folds (not just mean)
    """

    def __init__(self, config: Optional[CVConfig] = None) -> None:
        self.config = config or CVConfig()

    # -- Cross-Validate --

    async def cross_validate(
        self,
        model_factory: Callable[[], Any],
        train_fn: Callable,
        eval_fn: Callable,
        X: Any,
        y: Any,
        timestamps: List[datetime],
        config: Optional[CVConfig] = None,
    ) -> CVResult:
        """Run time-series cross-validation.

        Args:
            model_factory: () -> new model instance.
            train_fn: (model, X_train, y_train) -> trained model.
            eval_fn: (model, X_test, y_test) -> dict of metrics.
            X: Full feature matrix.
            y: Full labels.
            timestamps: Timestamps for each sample.
            config: CV configuration.

        Returns:
            CVResult with all fold metrics and aggregates.
        """
        import time
        import uuid

        cfg = config or self.config
        t0 = time.time()

        result = CVResult(
            cv_id=uuid.uuid4().hex[:12],
            method=cfg.method,
            n_splits=cfg.n_splits,
            started_at=datetime.utcnow(),
        )

        # Generate folds
        folds = self._generate_folds(timestamps, cfg)
        result.folds = folds

        # Run each fold
        for fold in folds:
            fold_metrics = await self._run_fold(
                model_factory, train_fn, eval_fn, X, y, timestamps, fold, cfg,
            )
            if fold_metrics:
                result.fold_metrics.append(fold_metrics)

        # Aggregate
        if result.fold_metrics:
            result.metrics_mean = {}
            result.metrics_std = {}
            for metric in cfg.metrics:
                values = [fm.get(metric, float('nan')) for fm in result.fold_metrics]
                valid = [v for v in values if v == v]  # filter NaN
                if valid:
                    result.metrics_mean[metric] = sum(valid) / len(valid)
                    result.metrics_std[metric] = (
                        sum((v - result.metrics_mean[metric])**2 for v in valid) / len(valid)
                    ) ** 0.5

        result.completed_at = datetime.utcnow()
        result.total_time_seconds = time.time() - t0

        logger.info("Cross-validation complete: %d folds, IC=%.4f±%.4f",
                     len(folds), result.metrics_mean.get("ic", 0), result.metrics_std.get("ic", 0))

        return result

    def _generate_folds(self, timestamps: List[datetime], config: CVConfig) -> List[CVFold]:
        """Generate time-series CV folds."""
        if not timestamps:
            return []

        if config.method == CVMethod.WALK_FORWARD:
            return self._walk_forward_folds(timestamps, config)
        else:
            return self._purged_kfold_folds(timestamps, config)

    def _purged_kfold_folds(self, timestamps: List[datetime], config: CVConfig) -> List[CVFold]:
        """Generate purged k-fold splits."""
        sorted_ts = sorted(set(timestamps))
        n = len(sorted_ts)
        folds: List[CVFold] = []

        if n < config.n_splits * config.min_train_days:
            logger.warning("Not enough data for %d-fold CV. Need %d days, have %d.",
                           config.n_splits, config.n_splits * config.min_train_days, n)
            return folds

        fold_size = n // config.n_splits

        for i in range(config.n_splits):
            test_start_idx = i * fold_size
            test_end_idx = min((i + 1) * fold_size, n)

            train_end_idx = max(0, test_start_idx - config.purge_days)
            train_start_idx = max(0, train_end_idx - config.min_train_days)

            folds.append(CVFold(
                fold_id=i + 1,
                train_start=sorted_ts[train_start_idx],
                train_end=sorted_ts[max(0, train_end_idx - 1)],
                test_start=sorted_ts[test_start_idx],
                test_end=sorted_ts[test_end_idx - 1],
                train_count=train_end_idx - train_start_idx,
                test_count=test_end_idx - test_start_idx,
            ))

        return folds

    def _walk_forward_folds(self, timestamps: List[datetime], config: CVConfig) -> List[CVFold]:
        """Generate walk-forward folds."""
        sorted_ts = sorted(set(timestamps))
        folds: List[CVFold] = []
        # Placeholder
        return folds

    async def _run_fold(
        self,
        model_factory: Callable,
        train_fn: Callable,
        eval_fn: Callable,
        X: Any, y: Any,
        timestamps: List[datetime],
        fold: CVFold,
        config: CVConfig,
    ) -> Optional[Dict[str, float]]:
        """Run a single CV fold."""
        try:
            # Placeholder: actual data slicing and training
            model = model_factory()
            # train_fn(model, X_train, y_train)
            # return eval_fn(model, X_test, y_test)
            return {}
        except Exception as exc:
            logger.warning("Fold %d failed: %s", fold.fold_id, exc)
            return None

    # -- Results Analysis --

    def check_overfitting(self, result: CVResult) -> Dict[str, Any]:
        """Check for overfitting by comparing train/val performance gap."""
        if len(result.fold_metrics) < 2:
            return {"overfitting_risk": "unknown"}

        scores = [fm.get(result.fold_metrics[0], 0) for fm in result.fold_metrics
                  if result.fold_metrics[0] in fm]
        first_score = scores[0] if scores else 0
        last_score = scores[-1] if scores else 0

        trend = "stable"
        if first_score > 0 and last_score > 0:
            ratio = last_score / max(first_score, 1e-8)
            if ratio < 0.5:
                trend = "degrading"
            elif ratio < 0.8:
                trend = "decaying"

        return {
            "first_fold_score": first_score,
            "last_fold_score": last_score,
            "score_trend": trend,
            "score_stability": result.score_stability,
            "overfitting_risk": "high" if result.score_stability < 0.5 else "low",
        }
