"""
ICYQuant Feature Definition - Standardized feature specification.

Provides a structured, reproducible definition format for all features.
Prevents ad-hoc, untracked factors in research code by enforcing a
standard schema: formula, input dataset, frequency, lookback, policies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .feature_registry import (
    FeatureCategory,
    FeatureFrequency,
    NullPolicy,
    OutlierPolicy,
)


# ---------------------------------------------------------------------------
# Feature Definition
# ---------------------------------------------------------------------------


@dataclass
class FeatureDefinition:
    """Standardized, immutable feature definition.

    Captures everything needed to reproduce a feature computation:

        Feature
         ├── Formula / Transform
         ├── Input Dataset(s)
         ├── Frequency
         ├── Timestamp Column
         ├── Lookback Window
         ├── Null Policy
         ├── Outlier Policy
         └── Version
    """

    # Identity
    name: str
    description: str = ""

    # Classification
    category: FeatureCategory = FeatureCategory.CUSTOM
    domain: str = ""  # e.g. "equity", "fixed_income", "macro"

    # Computation
    formula: str = ""           # SQL expression or Python lambda representation
    transform_type: str = ""    # rolling, cross_sectional, time_series, etc.
    input_columns: List[str] = field(default_factory=list)
    input_datasets: List[str] = field(default_factory=list)

    # Time
    timestamp_column: str = "trade_date"
    frequency: FeatureFrequency = FeatureFrequency.DAILY
    lookback_window: int = 20   # number of periods to look back
    lookback_unit: str = "d"    # d, h, m, w, M

    # Policies
    null_policy: NullPolicy = NullPolicy.FILL_FORWARD
    null_fill_value: Optional[float] = None

    outlier_policy: OutlierPolicy = OutlierPolicy.WINSORIZE
    outlier_lower_pct: float = 0.01
    outlier_upper_pct: float = 0.99
    outlier_std_multiplier: float = 3.0

    # Grouping
    group_by_columns: List[str] = field(default_factory=list)  # for cross-sectional features
    partition_by: Optional[str] = None  # e.g. sector, industry

    # Constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allow_nan: bool = False
    allow_inf: bool = False

    # Metadata
    owner: str = ""
    team: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    version: int = 1


    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "domain": self.domain,
            "formula": self.formula,
            "transform_type": self.transform_type,
            "input_columns": self.input_columns,
            "input_datasets": self.input_datasets,
            "timestamp_column": self.timestamp_column,
            "frequency": self.frequency.value,
            "lookback_window": self.lookback_window,
            "lookback_unit": self.lookback_unit,
            "null_policy": self.null_policy.value,
            "null_fill_value": self.null_fill_value,
            "outlier_policy": self.outlier_policy.value,
            "outlier_lower_pct": self.outlier_lower_pct,
            "outlier_upper_pct": self.outlier_upper_pct,
            "outlier_std_multiplier": self.outlier_std_multiplier,
            "group_by_columns": self.group_by_columns,
            "partition_by": self.partition_by,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allow_nan": self.allow_nan,
            "allow_inf": self.allow_inf,
            "owner": self.owner,
            "team": self.team,
            "tags": self.tags,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureDefinition":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            category=FeatureCategory(data.get("category", "custom")),
            domain=data.get("domain", ""),
            formula=data.get("formula", ""),
            transform_type=data.get("transform_type", ""),
            input_columns=data.get("input_columns", []),
            input_datasets=data.get("input_datasets", []),
            timestamp_column=data.get("timestamp_column", "trade_date"),
            frequency=FeatureFrequency(data.get("frequency", "1d")),
            lookback_window=data.get("lookback_window", 20),
            lookback_unit=data.get("lookback_unit", "d"),
            null_policy=NullPolicy(data.get("null_policy", "fill_forward")),
            null_fill_value=data.get("null_fill_value"),
            outlier_policy=OutlierPolicy(data.get("outlier_policy", "winsorize")),
            outlier_lower_pct=data.get("outlier_lower_pct", 0.01),
            outlier_upper_pct=data.get("outlier_upper_pct", 0.99),
            outlier_std_multiplier=data.get("outlier_std_multiplier", 3.0),
            group_by_columns=data.get("group_by_columns", []),
            partition_by=data.get("partition_by"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            allow_nan=data.get("allow_nan", False),
            allow_inf=data.get("allow_inf", False),
            owner=data.get("owner", ""),
            team=data.get("team", ""),
            tags=data.get("tags", {}),
            version=data.get("version", 1),
        )

    def content_hash(self) -> str:
        """Compute a deterministic hash of the definition content.

        The hash excludes metadata (version, owner) and only covers
        the computational definition. Two features with the same
        computational definition will have the same hash.
        """
        content = {
            "formula": self.formula,
            "transform_type": self.transform_type,
            "input_columns": sorted(self.input_columns),
            "input_datasets": sorted(self.input_datasets),
            "frequency": self.frequency.value,
            "lookback_window": self.lookback_window,
            "null_policy": self.null_policy.value,
            "outlier_policy": self.outlier_policy.value,
        }
        serialized = json.dumps(content, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    # -- Factory methods for common quant features --

    @classmethod
    def momentum(cls, name: str, window: int = 20, **kwargs: Any) -> "FeatureDefinition":
        """Create a momentum feature definition."""
        return cls(
            name=name,
            description=f"Momentum over {window} periods",
            category=FeatureCategory.MOMENTUM,
            formula=f"price.pct_change({window})",
            transform_type="rolling",
            lookback_window=window,
            **kwargs,
        )

    @classmethod
    def volatility(cls, name: str, window: int = 20, **kwargs: Any) -> "FeatureDefinition":
        """Create a volatility feature definition."""
        return cls(
            name=name,
            description=f"Volatility over {window} periods",
            category=FeatureCategory.VOLATILITY,
            formula=f"returns.rolling({window}).std()",
            transform_type="rolling",
            lookback_window=window,
            null_policy=NullPolicy.FILL_FORWARD,
            **kwargs,
        )

    @classmethod
    def zscore(cls, name: str, column: str, window: int = 252, **kwargs: Any) -> "FeatureDefinition":
        """Create a z-score feature definition."""
        return cls(
            name=name,
            description=f"Z-score of {column} over {window} periods",
            category=FeatureCategory.TECHNICAL,
            formula=f"({column} - {column}.rolling({window}).mean()) / {column}.rolling({window}).std()",
            transform_type="rolling",
            input_columns=[column],
            lookback_window=window,
            **kwargs,
        )

    @classmethod
    def cross_sectional_rank(cls, name: str, column: str, group_by: str = "sector", **kwargs: Any) -> "FeatureDefinition":
        """Create a cross-sectional rank feature."""
        return cls(
            name=name,
            description=f"Cross-sectional rank of {column} within {group_by}",
            category=FeatureCategory.CUSTOM,
            formula=f"{column}.rank(pct=True)",
            transform_type="cross_sectional",
            input_columns=[column],
            group_by_columns=[group_by] if group_by else [],
            **kwargs,
        )
