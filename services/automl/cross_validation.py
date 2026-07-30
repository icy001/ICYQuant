"""Time-Series Cross Validation.

Time-order-preserving cross-validation for financial data.
Expanding window splits that respect temporal structure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CVConfig:
    """Time-series CV configuration.

    Attributes:
        n_splits: Number of train/test splits.
        test_size: Size of each test fold (fraction or absolute).
        gap: Gap periods between train and test.
        min_train_size: Minimum training set size.
    """

    n_splits: int = 5
    test_size: float = 0.2
    gap: int = 0
    min_train_size: int = 100


@dataclass
class CVResult:
    """Result of time-series cross-validation."""

    fold_results: List[Dict[str, float]] = field(default_factory=list)
    mean_metrics: Dict[str, float] = field(default_factory=dict)
    std_metrics: Dict[str, float] = field(default_factory=dict)
    total_splits: int = 0
    elapsed_seconds: float = 0.0


class TimeSeriesCV:
    """Time-preserving cross-validation splitter.

    Generates expanding window splits where training always
    precedes testing, preventing look-ahead bias.
    """

    def __init__(self, config: Optional[CVConfig] = None) -> None:
        self.config = config or CVConfig()

    # ---- split generation ----

    def split(self, data_length: int) -> List[Tuple[int, int, int, int]]:
        """Generate (train_start, train_end, test_start, test_end) tuples.

        Returns:
            List of (train_start, train_end, test_start, test_end) indices.
        """
        cfg = self.config
        splits: List[Tuple[int, int, int, int]] = []

        if isinstance(cfg.test_size, float):
            test_len = max(1, int(data_length * cfg.test_size))
        else:
            test_len = int(cfg.test_size)

        initial_train = data_length - (test_len + cfg.gap) * cfg.n_splits
        if initial_train < cfg.min_train_size:
            return []

        for i in range(cfg.n_splits):
            train_end = initial_train + i * (test_len + cfg.gap)
            test_start = train_end + cfg.gap
            test_end = test_start + test_len

            if test_end > data_length:
                break

            splits.append((0, train_end, test_start, test_end))

        return splits

    def n_splits(self, data_length: int) -> int:
        return len(self.split(data_length))

    # ---- run ----

    def run(
        self,
        returns: List[float],
        predictions: Optional[List[float]] = None,
        targets: Optional[List[float]] = None,
    ) -> CVResult:
        """Run time-series cross-validation evaluation.

        Computes Sharpe and IC metrics per fold.

        Args:
            returns: Full return series.
            predictions: Model predictions (optional).
            targets: Actual targets (optional).

        Returns:
            CVResult with per-fold and aggregate metrics.
        """
        start = time.time()
        splits = self.split(len(returns))
        fold_results: List[Dict[str, float]] = []

        for fold_idx, (tr_start, tr_end, te_start, te_end) in enumerate(splits):
            train_returns = returns[tr_start:tr_end]
            test_returns = returns[te_start:te_end]

            fold_metrics: Dict[str, float] = {
                "fold": float(fold_idx),
                "train_sharpe": self._sharpe(train_returns),
                "test_sharpe": self._sharpe(test_returns),
                "train_mean": float(np.mean(train_returns)),
                "test_mean": float(np.mean(test_returns)),
                "train_std": float(np.std(train_returns)),
                "test_std": float(np.std(test_returns)),
            }

            # IC if predictions available
            if predictions is not None and targets is not None:
                test_preds = np.array(predictions[te_start:te_end], dtype=np.float64)
                test_targs = np.array(targets[te_start:te_end], dtype=np.float64)
                mask = ~np.isnan(test_preds) & ~np.isnan(test_targs)
                if mask.sum() >= 3:
                    ic = np.corrcoef(test_preds[mask], test_targs[mask])[0, 1]
                    fold_metrics["test_ic"] = float(ic)

            fold_results.append(fold_metrics)

        # Aggregate
        mean_metrics: Dict[str, float] = {}
        std_metrics: Dict[str, float] = {}
        metric_keys = set()
        for fr in fold_results:
            metric_keys.update(fr.keys())
        metric_keys.discard("fold")

        for key in metric_keys:
            values = [fr.get(key, float("nan")) for fr in fold_results]
            clean = [v for v in values if not np.isnan(v)]
            if clean:
                mean_metrics[key] = float(np.mean(clean))
                std_metrics[key] = float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0

        return CVResult(
            fold_results=fold_results,
            mean_metrics=mean_metrics,
            std_metrics=std_metrics,
            total_splits=len(fold_results),
            elapsed_seconds=time.time() - start,
        )

    # ---- helpers ----

    @staticmethod
    def _sharpe(returns: List[float], annualize: int = 252) -> float:
        arr = np.array(returns, dtype=np.float64)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 2 or np.std(arr) == 0:
            return 0.0
        return float(np.mean(arr) / np.std(arr, ddof=0) * np.sqrt(annualize))
