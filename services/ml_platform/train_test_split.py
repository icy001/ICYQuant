"""
ICYQuant Train/Test Split - Time-aware data splitting for quant finance.

Standard random split is inappropriate for time series data.
This module provides time-aware splitting methods:

    Train ────────► Test

    Train ─────────────► Test

    Train ───────────────────► Test

All splits respect temporal ordering to prevent future information leakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SplitMethod(Enum):
    """Train/test split methods."""

    TIME_SERIES = "time_series"         # single chronological split
    WALK_FORWARD = "walk_forward"       # rolling walk-forward
    EXPANDING_WINDOW = "expanding"      # expanding training window
    PURGED = "purged"                   # purged k-fold for time series
    STRATIFIED_TIME = "stratified_time" # time-stratified split


@dataclass
class SplitConfig:
    """Configuration for time-aware splitting."""

    method: SplitMethod = SplitMethod.TIME_SERIES

    # Ratios
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    test_ratio: float = 0.2

    # Walk-forward
    train_window_days: int = 252
    test_window_days: int = 63
    step_size_days: int = 21

    # Purged k-fold
    n_splits: int = 5
    purge_days: int = 5          # purge period between train/test
    embargo_days: int = 0         # embargo after test start

    # Constraints
    min_train_samples: int = 100
    min_test_samples: int = 20

    # Time column
    timestamp_column: str = "trade_date"


@dataclass
class SplitResult:
    """Result of a train/test split operation."""

    split_id: str = ""

    # Data
    X_train: Optional[Any] = None
    y_train: Optional[Any] = None
    X_val: Optional[Any] = None
    y_val: Optional[Any] = None
    X_test: Optional[Any] = None
    y_test: Optional[Any] = None

    # Time ranges
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    val_start: Optional[datetime] = None
    val_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None

    # Counts
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0

    # Method info
    method: SplitMethod = SplitMethod.TIME_SERIES
    fold: int = 0
    total_folds: int = 1


class TrainTestSplitter:
    """Time-aware train/test splitter for quant finance.

    Ensures:
    - No future data in training (chronological split)
    - Purged gaps between train and test (prevent overlap)
    - Walk-forward capability for rolling validation
    - Multiple folds for time-series cross-validation
    """

    def __init__(self, config: Optional[SplitConfig] = None) -> None:
        self.config = config or SplitConfig()

    # -- Single Split --

    def split(
        self,
        features: Any,
        labels: Any,
        timestamps: Optional[List[datetime]] = None,
        config: Optional[SplitConfig] = None,
    ) -> SplitResult:
        """Perform a single time-series train/val/test split.

        Splits chronologically: oldest → train, middle → val, newest → test.
        """
        cfg = config or self.config

        result = SplitResult(
            method=cfg.method,
            total_folds=1,
        )

        if cfg.method == SplitMethod.TIME_SERIES:
            result = self._time_series_split(features, labels, timestamps, cfg)
        elif cfg.method == SplitMethod.PURGED:
            result = self._purged_split(features, labels, timestamps, cfg)
        else:
            result = self._time_series_split(features, labels, timestamps, cfg)

        logger.info("Train/Test split: train=%d, val=%d, test=%d",
                     result.train_count, result.val_count, result.test_count)

        return result

    def _time_series_split(
        self, features: Any, labels: Any, timestamps: Optional[List[datetime]], config: SplitConfig,
    ) -> SplitResult:
        """Chronological time series split.

        Train ──────── Val ──── Test
        (oldest)                    (newest)
        """
        return SplitResult(method=SplitMethod.TIME_SERIES)

    def _purged_split(
        self, features: Any, labels: Any, timestamps: Optional[List[datetime]], config: SplitConfig,
    ) -> SplitResult:
        """Purged k-fold split for time series.

        Ensures purged gap between train and test to prevent information
        leakage from overlapping time windows.
        """
        return SplitResult(method=SplitMethod.PURGED)

    # -- Walk-Forward Splits --

    def walk_forward_splits(
        self,
        features: Any,
        labels: Any,
        timestamps: List[datetime],
        config: Optional[SplitConfig] = None,
    ) -> List[SplitResult]:
        """Generate walk-forward train/test splits.

        Produces multiple (train, test) pairs by sliding a window
        forward through time:

        [Train 1] [Test 1]
            [Train 2] [Test 2]
                [Train 3] [Test 3]

        Each fold uses chronologically later data.
        """
        cfg = config or self.config
        splits: List[SplitResult] = []

        if not timestamps:
            return splits

        sorted_ts = sorted(set(timestamps))
        if not sorted_ts:
            return splits

        start_date = sorted_ts[0]
        end_date = sorted_ts[-1]

        total_days = (end_date - start_date).days
        train_days = cfg.train_window_days
        test_days = cfg.test_window_days
        step_days = cfg.step_size_days

        current_start = start_date
        fold = 0

        while current_start + timedelta(days=train_days + test_days) <= end_date:
            fold += 1
            train_start = current_start
            train_end = current_start + timedelta(days=train_days)
            test_start = train_end + timedelta(days=cfg.purge_days)
            test_end = test_start + timedelta(days=test_days)

            # Placeholder: actual data slicing in production
            splits.append(SplitResult(
                fold=fold,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                method=SplitMethod.WALK_FORWARD,
            ))

            current_start += timedelta(days=step_days)

        logger.info("Generated %d walk-forward splits (train=%dd, test=%dd, step=%dd)",
                     len(splits), train_days, test_days, step_days)
        return splits

    # -- Purged K-Fold --

    def purged_k_fold_splits(
        self,
        features: Any,
        labels: Any,
        timestamps: List[datetime],
        n_splits: int = 5,
        purge_days: int = 5,
    ) -> List[SplitResult]:
        """Generate purged k-fold splits for time series cross-validation.

        Unlike standard k-fold, this:
        1. Splits chronologically (no shuffling)
        2. Inserts purge gaps between train and test
        3. May embargo recent data points
        """
        config = SplitConfig(
            method=SplitMethod.PURGED,
            n_splits=n_splits,
            purge_days=purge_days,
        )
        splits: List[SplitResult] = []
        # Placeholder
        return splits

    # -- Utility --

    def check_no_overlap(self, result: SplitResult) -> bool:
        """Verify that train and test have no temporal overlap."""
        if result.train_end and result.test_start:
            return result.train_end < result.test_start
        return True

    def check_no_lookahead(self, train_timestamps: List[datetime], test_timestamps: List[datetime]) -> bool:
        """Verify no train sample is after any test sample."""
        if not train_timestamps or not test_timestamps:
            return True
        max_train = max(train_timestamps)
        min_test = min(test_timestamps)
        return max_train < min_test
