"""Walk-Forward Validator.

Time-series-aware rolling train/test validation to prevent
overfitting and ensure out-of-sample robustness.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation.

    Attributes:
        train_window: Number of periods for training.
        test_window: Number of periods for testing.
        step_size: How many periods to advance each window.
        min_train_size: Minimum training data required.
        anchored: If True, training window expands (anchored). Else rolling.
        gap: Gap between train and test to avoid leakage.
    """

    train_window: int = 252 * 3  # 3 years daily
    test_window: int = 252       # 1 year
    step_size: int = 63          # quarterly
    min_train_size: int = 252    # 1 year minimum
    anchored: bool = True
    gap: int = 0


@dataclass
class WindowResult:
    """Result for a single walk-forward window."""

    window_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)
    model_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    """Aggregate walk-forward validation result."""

    window_results: List[WindowResult] = field(default_factory=list)
    aggregate_train_metrics: Dict[str, float] = field(default_factory=dict)
    aggregate_test_metrics: Dict[str, float] = field(default_factory=dict)
    stability_score: float = 0.0
    is_robust: bool = False
    n_windows: int = 0
    elapsed_seconds: float = 0.0


class WalkForwardValidator:
    """Time-series walk-forward cross-validation.

    Ensures temporal ordering is preserved: training always
    precedes testing.
    """

    def __init__(self, config: Optional[WalkForwardConfig] = None) -> None:
        self.config = config or WalkForwardConfig()

    # ---- window generation ----

    def generate_windows(self, data_length: int) -> List[WindowResult]:
        """Generate walk-forward window definitions.

        Returns list of WindowResult with indices only (no metrics yet).
        """
        cfg = self.config
        windows: List[WindowResult] = []

        if data_length < cfg.min_train_size + cfg.test_window:
            return windows

        idx = 0
        train_start = 0

        while True:
            if cfg.anchored:
                train_end = cfg.train_window + idx * cfg.step_size
            else:
                train_end = train_start + cfg.train_window

            test_start = train_end + cfg.gap
            test_end = test_start + cfg.test_window

            if test_end > data_length:
                break
            if train_end - train_start < cfg.min_train_size:
                break

            wr = WindowResult(
                window_index=idx,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
            windows.append(wr)

            if not cfg.anchored:
                train_start += cfg.step_size
            idx += 1

        return windows

    def window_count(self, data_length: int) -> int:
        return len(self.generate_windows(data_length))

    # ---- run ----

    def run(
        self,
        data: List[Any],
        train_fn: Callable[[List[Any]], Dict[str, Any]],
        eval_fn: Callable[[Any, Dict[str, Any]], Dict[str, float]],
    ) -> WalkForwardResult:
        """Execute walk-forward validation.

        Args:
            data: Complete time-series data.
            train_fn: (train_subset) -> model_info dict.
            eval_fn: (test_element, model_info) -> metrics dict.

        Returns:
            WalkForwardResult.
        """
        start = time.time()
        windows = self.generate_windows(len(data))
        results: List[WindowResult] = []

        for wr in windows:
            train_data = data[wr.train_start : wr.train_end]
            test_data = data[wr.test_start : wr.test_end]

            model_info = train_fn(train_data)

            # Evaluate on train (in-sample)
            train_metrics: Dict[str, float] = {}
            # Evaluate on test (out-of-sample)
            test_metrics: Dict[str, float] = {}
            for item in test_data:
                m = eval_fn(item, model_info)
                for k, v in m.items():
                    test_metrics.setdefault(k, []).append(v)  # type: ignore

            wr.train_metrics = train_metrics
            # Average test metrics
            wr.test_metrics = {k: float(np.mean(v)) for k, v in test_metrics.items()}  # type: ignore
            wr.model_info = model_info
            results.append(wr)

        # Aggregate
        agg_train: Dict[str, List[float]] = {}
        agg_test: Dict[str, List[float]] = {}
        for wr in results:
            for k, v in wr.test_metrics.items():
                agg_test.setdefault(k, []).append(v)
            for k, v in wr.train_metrics.items():
                agg_train.setdefault(k, []).append(v)

        aggregate_test = {k: float(np.mean(v)) for k, v in agg_test.items()}
        aggregate_train = {k: float(np.mean(v)) for k, v in agg_train.items()}

        # Stability: 1 - CV of test sharpe across windows
        test_sharpes = [wr.test_metrics.get("sharpe", 0) for wr in results]
        stability = self._compute_stability(test_sharpes)

        n = len(results)
        is_robust = n >= 3 and stability >= 0.5

        return WalkForwardResult(
            window_results=results,
            aggregate_train_metrics=aggregate_train,
            aggregate_test_metrics=aggregate_test,
            stability_score=stability,
            is_robust=is_robust,
            n_windows=n,
            elapsed_seconds=time.time() - start,
        )

    def run_simple(
        self,
        returns: List[float],
        eval_fn: Callable[[List[float]], Dict[str, float]],
    ) -> WalkForwardResult:
        """Simplified walk-forward using returns only.

        Args:
            returns: Full return series.
            eval_fn: (returns_subset) -> metrics dict.
        """
        return self.run(
            data=returns,
            train_fn=lambda d: {"n": len(d)},
            eval_fn=lambda item, info: eval_fn([item]),
        )

    # ---- helpers ----

    @staticmethod
    def _compute_stability(values: List[float]) -> float:
        arr = np.array(values, dtype=np.float64)
        if len(arr) < 2:
            return 0.0
        mean_v = float(np.mean(arr))
        std_v = float(np.std(arr, ddof=1))
        if abs(mean_v) < 1e-10:
            return 0.0
        cv = std_v / abs(mean_v)
        return float(max(0.0, 1.0 - cv))
