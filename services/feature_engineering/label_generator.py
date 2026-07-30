"""Label Generator.

Generates supervised learning labels from raw market data.
Supports regression, classification, and learning-to-rank labels.

Usage::

    from services.feature_engineering import RegressionLabelGenerator

    gen = RegressionLabelGenerator(horizon=5, target_col="close")
    labels = gen.generate(df)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class LabelType(str, Enum):
    """Type of supervised learning label."""

    REGRESSION = "regression"       # continuous target
    BINARY_CLASSIFICATION = "binary_classification"  # up/down
    MULTICLASS_CLASSIFICATION = "multiclass_classification"  # up/flat/down
    RANKING = "ranking"             # learning-to-rank


@dataclass
class LabelConfig:
    """Configuration for label generation.

    Attributes:
        horizon: Forward-looking periods for label.
        target_col: Column name to derive labels from.
        threshold: Threshold for binary classification (as fraction).
        bins: Number of bins for multiclass classification.
        smoothing: Apply exponential smoothing to target before labeling.
    """

    horizon: int = 5
    target_col: str = "close"
    threshold: float = 0.0  # fraction, e.g. 0.005 = 0.5%
    bins: int = 3
    smoothing: bool = False
    smoothing_alpha: float = 0.3


@dataclass
class LabelResult:
    """Result of label generation."""

    labels: List[float]
    label_type: LabelType
    config: LabelConfig
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"LabelResult(type={self.label_type.value}, n={len(self.labels)})"


# ---- base ----

class BaseLabelGenerator:
    """Abstract base for label generators."""

    label_type: LabelType

    def __init__(self, config: Optional[LabelConfig] = None) -> None:
        self.config = config or LabelConfig()

    def generate(self, values: List[float]) -> LabelResult:
        """Generate labels from price/value series."""
        raise NotImplementedError

    def _compute_forward_return(self, values: List[float]) -> List[float]:
        """Compute forward returns for labeling."""
        horizon = self.config.horizon
        n = len(values)
        fwd_ret = [float("nan")] * n
        for i in range(n - horizon):
            if values[i] and values[i + horizon] and values[i] != 0:
                fwd_ret[i] = (values[i + horizon] - values[i]) / values[i]
            else:
                fwd_ret[i] = float("nan")
        return fwd_ret

    def _smooth(self, values: List[float]) -> List[float]:
        """Apply exponential smoothing."""
        if not self.config.smoothing:
            return list(values)
        alpha = self.config.smoothing_alpha
        smoothed = [values[0] if values[0] is not None else 0.0]
        for v in values[1:]:
            if v is None or np.isnan(v):
                smoothed.append(smoothed[-1])
            else:
                smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
        return smoothed


# ---- Regression ----

class RegressionLabelGenerator(BaseLabelGenerator):
    """Generate continuous forward-return labels for regression tasks.

    label_i = (price_{i+horizon} - price_i) / price_i
    """

    label_type = LabelType.REGRESSION

    def generate(self, values: List[float]) -> LabelResult:
        smoothed = self._smooth(values)
        fwd_ret = self._compute_forward_return(smoothed)
        return LabelResult(
            labels=fwd_ret,
            label_type=self.label_type,
            config=self.config,
            metadata={"horizon": self.config.horizon, "target": self.config.target_col},
        )


# ---- Classification ----

class ClassificationLabelGenerator(BaseLabelGenerator):
    """Generate classification labels from forward returns.

    Binary: 1 (up >= threshold), 0 (down < -threshold), nan (flat)
    Multiclass: discretized into bins by quantile.
    """

    label_type = LabelType.BINARY_CLASSIFICATION

    def __init__(
        self,
        config: Optional[LabelConfig] = None,
        num_classes: int = 2,
        class_labels: Optional[List[str]] = None,
    ) -> None:
        super().__init__(config)
        self.num_classes = num_classes
        self.class_labels = class_labels

    def generate(self, values: List[float]) -> LabelResult:
        smoothed = self._smooth(values)
        fwd_ret = self._compute_forward_return(smoothed)

        if self.num_classes == 2:
            return self._binary_labels(fwd_ret)
        else:
            return self._multiclass_labels(fwd_ret)

    def _binary_labels(self, fwd_ret: List[float]) -> LabelResult:
        threshold = self.config.threshold
        labels: List[float] = []
        for r in fwd_ret:
            if np.isnan(r):
                labels.append(float("nan"))
            elif r >= threshold:
                labels.append(1.0)
            elif r <= -threshold:
                labels.append(0.0)
            else:
                labels.append(float("nan"))  # flat region excluded
        lt = LabelType.BINARY_CLASSIFICATION
        return LabelResult(
            labels=labels, label_type=lt, config=self.config,
            metadata={"threshold": threshold, "num_classes": 2},
        )

    def _multiclass_labels(self, fwd_ret: List[float]) -> LabelResult:
        clean = [r for r in fwd_ret if not np.isnan(r)]
        if len(clean) < self.num_classes:
            return LabelResult(
                labels=[float("nan")] * len(fwd_ret),
                label_type=LabelType.MULTICLASS_CLASSIFICATION,
                config=self.config,
                metadata={"num_classes": self.num_classes, "error": "insufficient data"},
            )

        bins = self.config.bins
        percentiles = np.linspace(0, 100, bins + 1)[1:-1]
        thresholds = [float(np.percentile(clean, p)) for p in percentiles]

        labels: List[float] = []
        for r in fwd_ret:
            if np.isnan(r):
                labels.append(float("nan"))
            else:
                cls = 0
                for t in thresholds:
                    if r >= t:
                        cls += 1
                labels.append(float(cls))

        lt = LabelType.MULTICLASS_CLASSIFICATION
        return LabelResult(
            labels=labels, label_type=lt, config=self.config,
            metadata={"num_classes": bins, "thresholds": thresholds},
        )


# ---- Ranking ----

class RankingLabelGenerator(BaseLabelGenerator):
    """Generate learning-to-rank labels.

    Labels are percentile ranks of forward returns within each
    cross-sectional group (e.g. all symbols on a given day).
    """

    label_type = LabelType.RANKING

    def __init__(self, config: Optional[LabelConfig] = None) -> None:
        super().__init__(config)
        self.config.horizon = config.horizon if config else 5

    def generate(self, values: List[float]) -> LabelResult:
        fwd_ret = self._compute_forward_return(values)
        clean = [(i, r) for i, r in enumerate(fwd_ret) if not np.isnan(r)]

        if len(clean) < 2:
            return LabelResult(
                labels=[float("nan")] * len(values),
                label_type=self.label_type,
                config=self.config,
                metadata={"error": "insufficient data for ranking"},
            )

        # Sort by return, assign ranks
        sorted_pairs = sorted(clean, key=lambda x: x[1])
        n = len(sorted_pairs)
        ranks = [0.0] * n
        for rank_idx, (orig_idx, _) in enumerate(sorted_pairs):
            ranks[rank_idx] = (rank_idx + 1) / n  # normalized rank

        labels = [float("nan")] * len(values)
        for (orig_idx, _), rank_val in zip(sorted_pairs, ranks):
            labels[orig_idx] = rank_val

        return LabelResult(
            labels=labels,
            label_type=self.label_type,
            config=self.config,
            metadata={"horizon": self.config.horizon, "n_ranked": len(clean)},
        )

    def generate_cross_sectional(
        self, values_matrix: List[List[float]]
    ) -> List[LabelResult]:
        """Generate ranking labels across multiple symbols for each time step.

        Args:
            values_matrix: List of symbol series, each being List[float] of same length.
                          Shape: (n_symbols, n_timesteps)

        Returns:
            List of LabelResult, one per symbol.
        """
        n_symbols = len(values_matrix)
        n_steps = max(len(v) for v in values_matrix) if values_matrix else 0

        # Transpose: (n_timesteps, n_symbols)
        results_per_symbol: List[List[float]] = [[] for _ in range(n_symbols)]

        for t in range(n_steps):
            # Collect values at time t across all symbols
            cross: List[Tuple[int, float]] = []
            for s in range(n_symbols):
                if t < len(values_matrix[s]):
                    val = values_matrix[s][t]
                    if val is not None and not np.isnan(val):
                        cross.append((s, val))
            # Rank within this time step
            if len(cross) >= 2:
                sorted_cross = sorted(cross, key=lambda x: x[1])
                n = len(sorted_cross)
                for rank_idx, (sym, _) in enumerate(sorted_cross):
                    results_per_symbol[sym].append((rank_idx + 1) / n)
            else:
                for s in range(n_symbols):
                    results_per_symbol[s].append(float("nan"))

        return [
            LabelResult(
                labels=results_per_symbol[s],
                label_type=self.label_type,
                config=self.config,
                metadata={"symbol_index": s, "horizon": self.config.horizon},
            )
            for s in range(n_symbols)
        ]
