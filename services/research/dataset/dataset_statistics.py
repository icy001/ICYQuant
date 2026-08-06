"""Dataset Statistics — descriptive and inferential statistics for datasets.

Provides column-level statistical measures including distribution analysis,
correlation computation, and summary statistics for quantitative research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4


class StatisticLevel(str, Enum):
    """Granularity of statistical computation."""

    DATASET = "dataset"
    COLUMN = "column"
    ROW = "row"
    WINDOW = "window"  # Rolling/time-window statistics


class DistributionType(str, Enum):
    """Common distribution shapes."""

    NORMAL = "normal"
    UNIFORM = "uniform"
    SKEWED_LEFT = "skewed_left"
    SKEWED_RIGHT = "skewed_right"
    BIMODAL = "bimodal"
    MULTIMODAL = "multimodal"
    EXPONENTIAL = "exponential"
    UNKNOWN = "unknown"


@dataclass
class ColumnStatistics:
    """Comprehensive statistics for a single column.

    Includes central tendency, dispersion, shape, and distribution
    measures commonly used in quantitative research.
    """

    column_name: str = ""
    count: int = 0
    null_count: int = 0
    null_ratio: float = 0.0

    # Central tendency
    mean: Optional[float] = None
    median: Optional[float] = None
    mode: Optional[Any] = None
    trimmed_mean: Optional[float] = None  # Mean excluding top/bottom 5%

    # Dispersion
    std: Optional[float] = None
    variance: Optional[float] = None
    mad: Optional[float] = None       # Median Absolute Deviation
    range: Tuple[Optional[float], Optional[float]] = (None, None)
    iqr: Optional[float] = None        # Inter-quartile range

    # Shape
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    distribution_type: DistributionType = DistributionType.UNKNOWN

    # Quantiles
    min_value: Optional[float] = None
    p1: Optional[float] = None
    p5: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    max_value: Optional[float] = None

    # Outlier detection
    outlier_count: int = 0
    outlier_ratio: float = 0.0
    outlier_threshold: float = 3.0  # IQR multiplier

    # Stability
    coefficient_of_variation: Optional[float] = None  # std / mean
    jarque_bera_stat: Optional[float] = None
    jarque_bera_pvalue: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_normal(self) -> bool:
        return self.distribution_type == DistributionType.NORMAL

    @property
    def has_outliers(self) -> bool:
        return self.outlier_ratio > 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_name": self.column_name,
            "count": self.count,
            "null_count": self.null_count,
            "null_ratio": self.null_ratio,
            "mean": self.mean,
            "median": self.median,
            "mode": self.mode,
            "trimmed_mean": self.trimmed_mean,
            "std": self.std,
            "variance": self.variance,
            "mad": self.mad,
            "range": list(self.range),
            "iqr": self.iqr,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "distribution_type": self.distribution_type.value,
            "min_value": self.min_value,
            "p1": self.p1, "p5": self.p5, "p10": self.p10,
            "p25": self.p25, "p50": self.p50, "p75": self.p75,
            "p90": self.p90, "p95": self.p95, "p99": self.p99,
            "max_value": self.max_value,
            "outlier_count": self.outlier_count,
            "outlier_ratio": self.outlier_ratio,
            "outlier_threshold": self.outlier_threshold,
            "coefficient_of_variation": self.coefficient_of_variation,
            "jarque_bera_stat": self.jarque_bera_stat,
            "jarque_bera_pvalue": self.jarque_bera_pvalue,
        }

    def __repr__(self) -> str:
        return (
            f"ColumnStatistics(col={self.column_name}, n={self.count}, "
            f"mean={self.mean}, std={self.std}, skew={self.skewness})"
        )


@dataclass
class DatasetStatistics:
    """Aggregated statistics for an entire dataset.

    Provides column-level statistics plus dataset-wide metrics
    for cross-sectional analysis and quality monitoring.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    dataset_version: int = 1
    level: StatisticLevel = StatisticLevel.DATASET
    row_count: int = 0
    column_count: int = 0
    columns: List[ColumnStatistics] = field(default_factory=list)
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    covariance_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    vif: Dict[str, float] = field(default_factory=dict)
    condition_number: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    computation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_column(self, name: str) -> Optional[ColumnStatistics]:
        """Get statistics for a specific column."""
        for col in self.columns:
            if col.column_name == name:
                return col
        return None

    def highly_correlated_pairs(self, threshold: float = 0.8) -> List[Tuple[str, str, float]]:
        """Find column pairs with correlation above threshold."""
        pairs: List[Tuple[str, str, float]] = []
        seen: set = set()
        for col_a, correlations in self.correlation_matrix.items():
            for col_b, corr in correlations.items():
                if col_a != col_b and abs(corr) >= threshold:
                    key = tuple(sorted([col_a, col_b]))
                    if key not in seen:
                        seen.add(key)
                        pairs.append((col_a, col_b, corr))
        return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

    def outlier_summary(self) -> Dict[str, int]:
        """Count of outliers per column."""
        return {c.column_name: c.outlier_count for c in self.columns if c.has_outliers}

    def summary(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.dataset_version,
            "rows": self.row_count,
            "columns": self.column_count,
            "highly_correlated_pairs": len(self.highly_correlated_pairs()),
            "outlier_columns": len(self.outlier_summary()),
            "computation_time_ms": self.computation_time_ms,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "level": self.level.value,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [c.to_dict() for c in self.columns],
            "correlation_matrix": self.correlation_matrix,
            "covariance_matrix": self.covariance_matrix,
            "vif": self.vif,
            "condition_number": self.condition_number,
            "created_at": self.created_at.isoformat(),
            "computation_time_ms": self.computation_time_ms,
        }

    def __repr__(self) -> str:
        return (
            f"DatasetStatistics(dataset={self.dataset_id[:8]}, "
            f"v{self.dataset_version}, cols={self.column_count})"
        )
