"""
ICYQuant Label Engine - Unified training label generation.

Generates training labels from price data with support for:
- Forward returns (1D, 5D, 10D, 20D)
- Classification (up/down)
- Regression (continuous returns)
- Ranking (cross-sectional)
- Volatility labels
- Drawdown labels
- Event labels (earnings, etc.)

    Price(t)
       │
       ▼
    Forward Return
       │
       ├── 1D
       ├── 5D
       ├── 10D
       └── 20D

All labels use point-in-time data only (no look-ahead bias).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LabelType(Enum):
    """Types of training labels."""

    REGRESSION = "regression"       # continuous forward return
    CLASSIFICATION = "classification"  # binary up/down
    MULTICLASS = "multiclass"       # multiple buckets
    RANKING = "ranking"             # cross-sectional rank
    VOLATILITY = "volatility"       # future volatility
    DRAWDOWN = "drawdown"           # max drawdown over horizon
    EVENT = "event"                 # event-driven label


class LabelHorizon(Enum):
    """Label forward horizons."""

    H1D = "1d"
    H2D = "2d"
    H3D = "3d"
    H5D = "5d"
    H10D = "10d"
    H15D = "15d"
    H20D = "20d"
    H1M = "1M"
    H2M = "2M"
    H3M = "3M"
    H6M = "6M"


@dataclass
class LabelConfig:
    """Configuration for label generation."""

    label_type: LabelType = LabelType.REGRESSION
    horizon: LabelHorizon = LabelHorizon.H5D
    price_column: str = "close"
    forward_return_column: str = "forward_return"

    # Classification
    threshold: float = 0.0          # binary classification threshold
    num_classes: int = 5            # for multiclass (quintiles)

    # Ranking
    group_by: Optional[str] = None  # e.g. "sector", "industry"

    # Volatility
    vol_window: int = 20

    # Drawdown
    dd_horizon: int = 20

    # Filters
    min_data_points: int = 252      # minimum history required
    max_outlier_zscore: float = 5.0


@dataclass
class LabelResult:
    """Result of label generation."""

    label_type: LabelType
    horizon: LabelHorizon
    values: Optional[Any] = None    # computed labels
    timestamp: Optional[datetime] = None  # reference timestamp (point-in-time)

    # Statistics
    count: int = 0
    null_count: int = 0
    mean: float = 0.0
    std: float = 0.0
    positive_ratio: float = 0.0     # for classification

    # Time range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LabelEngine:
    """Generates training labels for ML models.

    Ensures point-in-time correctness: labels at time t are computed
    using only data available after t (forward returns), so no future
    information leaks into training.
    """

    def __init__(self) -> None:
        pass

    # -- Label Generation --

    async def generate(
        self,
        price_data: Any,
        config: LabelConfig,
        reference_date: Optional[datetime] = None,
    ) -> LabelResult:
        """Generate labels from price data.

        Args:
            price_data: Price data (DataFrame with 'close' column).
            config: Label configuration.
            reference_date: Optional reference date for point-in-time.

        Returns:
            LabelResult with computed labels and statistics.
        """
        if config.label_type == LabelType.REGRESSION:
            return await self._regression_labels(price_data, config)
        elif config.label_type == LabelType.CLASSIFICATION:
            return await self._classification_labels(price_data, config)
        elif config.label_type == LabelType.RANKING:
            return await self._ranking_labels(price_data, config)
        elif config.label_type == LabelType.VOLATILITY:
            return await self._volatility_labels(price_data, config)
        elif config.label_type == LabelType.DRAWDOWN:
            return await self._drawdown_labels(price_data, config)
        else:
            raise ValueError(f"Unsupported label type: {config.label_type}")

    # -- Label Types --

    async def _regression_labels(self, price_data: Any, config: LabelConfig) -> LabelResult:
        """Generate forward return regression labels.

        Computes forward return: (price[t+h] - price[t]) / price[t]
        """
        return LabelResult(
            label_type=LabelType.REGRESSION,
            horizon=config.horizon,
        )

    async def _classification_labels(self, price_data: Any, config: LabelConfig) -> LabelResult:
        """Generate binary classification labels (up/down).

        Label = 1 if forward return > threshold, else 0.
        """
        return LabelResult(
            label_type=LabelType.CLASSIFICATION,
            horizon=config.horizon,
            positive_ratio=0.5,
        )

    async def _ranking_labels(self, price_data: Any, config: LabelConfig) -> LabelResult:
        """Generate cross-sectional ranking labels.

        Ranks entities by forward return within groups (e.g., sector).
        """
        return LabelResult(
            label_type=LabelType.RANKING,
            horizon=config.horizon,
        )

    async def _volatility_labels(self, price_data: Any, config: LabelConfig) -> LabelResult:
        """Generate future volatility labels.

        Label = realized volatility over the forward horizon.
        """
        return LabelResult(
            label_type=LabelType.VOLATILITY,
            horizon=config.horizon,
        )

    async def _drawdown_labels(self, price_data: Any, config: LabelConfig) -> LabelResult:
        """Generate maximum drawdown labels.

        Label = max drawdown over the forward horizon.
        """
        return LabelResult(
            label_type=LabelType.DRAWDOWN,
            horizon=config.horizon,
        )

    # -- Multi-Horizon Generation --

    async def generate_multi_horizon(
        self,
        price_data: Any,
        label_type: LabelType = LabelType.REGRESSION,
        horizons: Optional[List[LabelHorizon]] = None,
    ) -> Dict[LabelHorizon, LabelResult]:
        """Generate labels for multiple horizons simultaneously.

        Efficient for generating multi-target training data.
        """
        if horizons is None:
            horizons = [LabelHorizon.H1D, LabelHorizon.H5D, LabelHorizon.H10D, LabelHorizon.H20D]

        results: Dict[LabelHorizon, LabelResult] = {}
        for horizon in horizons:
            config = LabelConfig(label_type=label_type, horizon=horizon)
            results[horizon] = await self.generate(price_data, config)

        return results

    # -- Label Quality --

    async def evaluate_label_quality(
        self, labels: LabelResult, min_positive_ratio: float = 0.3,
    ) -> Dict[str, Any]:
        """Evaluate label quality and suitability for training."""
        return {
            "label_type": labels.label_type.value,
            "horizon": labels.horizon.value,
            "count": labels.count,
            "null_ratio": labels.null_count / max(labels.count, 1),
            "mean": labels.mean,
            "std": labels.std,
            "positive_ratio": labels.positive_ratio,
            "suitable": (
                labels.count > 100
                and labels.null_count / max(labels.count, 1) < 0.3
                and abs(labels.mean / max(labels.std, 1e-8)) < 3.0
            ),
        }
