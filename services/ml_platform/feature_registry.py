"""
ICYQuant Feature Registry - Centralized feature metadata management.

Unified registration of all factors and features used across the platform.
Every feature has: ID, definition, data source, frequency, lookback,
version, owner, quality score, and full lineage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FeatureCategory(Enum):
    """Feature categories for the quant domain."""

    PRICE = "price"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    SENTIMENT = "sentiment"
    MACRO = "macro"
    ALTERNATIVE = "alternative"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    CUSTOM = "custom"


class FeatureFrequency(Enum):
    """Feature computation frequency."""

    TICK = "tick"
    MINUTE = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"
    QUARTERLY = "1Q"
    ANNUAL = "1Y"


class NullPolicy(Enum):
    """How to handle null/NaN values."""

    DROP = "drop"
    FILL_ZERO = "fill_zero"
    FILL_MEAN = "fill_mean"
    FILL_MEDIAN = "fill_median"
    FILL_FORWARD = "fill_forward"
    FILL_BACKWARD = "fill_backward"
    KEEP = "keep"
    RAISE = "raise"


class OutlierPolicy(Enum):
    """How to handle outliers."""

    CLIP = "clip"        # Clip to [lower, upper]
    WINSORIZE = "winsorize"
    STANDARDIZE = "standardize"
    LOG_TRANSFORM = "log_transform"
    KEEP = "keep"
    DROP = "drop"


# ---------------------------------------------------------------------------
# Feature Entry
# ---------------------------------------------------------------------------


@dataclass
class FeatureEntry:
    """Complete feature metadata entry in the registry.

    Every feature is fully described to ensure reproducibility
    and prevent ad-hoc untracked factors in research code.
    """

    feature_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Classification
    category: FeatureCategory = FeatureCategory.CUSTOM
    domain: str = ""

    # Computation
    formula: str = ""
    input_datasets: List[str] = field(default_factory=list)
    frequency: FeatureFrequency = FeatureFrequency.DAILY
    lookback_window: int = 0  # number of periods
    required_columns: List[str] = field(default_factory=list)

    # Policies
    null_policy: NullPolicy = NullPolicy.FILL_FORWARD
    outlier_policy: OutlierPolicy = OutlierPolicy.WINSORIZE
    outlier_lower_pct: float = 0.01
    outlier_upper_pct: float = 0.99

    # Versioning
    version: int = 1
    latest_version_id: Optional[str] = None

    # Ownership
    owner: str = ""
    team: str = ""

    # Quality
    quality_score: float = 0.0
    coverage: float = 1.0
    last_computed: Optional[datetime] = None
    data_freshness: Optional[datetime] = None

    # Lineage
    upstream_features: List[str] = field(default_factory=list)
    downstream_features: List[str] = field(default_factory=list)
    upstream_datasets: List[str] = field(default_factory=list)

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deprecated: bool = False


# ---------------------------------------------------------------------------
# Feature Registry
# ---------------------------------------------------------------------------


class FeatureRegistry:
    """Centralized registry for all features used in the platform.

    Maintains indices for fast lookup:
    - by_id: direct feature lookup
    - by_name: name-based lookup
    - by_category: domain-specific feature sets
    - by_tag: tag-based filtering
    - lineage_index: upstream/downstream tracking
    """

    def __init__(self) -> None:
        self._features: Dict[str, FeatureEntry] = {}
        self._name_index: Dict[str, str] = {}       # name -> feature_id
        self._category_index: Dict[FeatureCategory, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._lineage_index: Dict[str, List[str]] = {}  # feature_id -> [dependent_ids]

    # -- Registration --

    def register(self, feature: FeatureEntry) -> str:
        """Register a feature in the registry."""
        if feature.name and feature.name in self._name_index:
            existing_id = self._name_index[feature.name]
            logger.warning("Feature name '%s' already exists (id=%s), overwriting", feature.name, existing_id)

        feature.updated_at = datetime.utcnow()
        self._features[feature.feature_id] = feature

        # Update indices
        if feature.name:
            self._name_index[feature.name] = feature.feature_id

        cat = feature.category
        if cat not in self._category_index:
            self._category_index[cat] = []
        if feature.feature_id not in self._category_index[cat]:
            self._category_index[cat].append(feature.feature_id)

        for tag_key, tag_val in feature.tags.items():
            tag_entry = f"{tag_key}:{tag_val}"
            if tag_entry not in self._tag_index:
                self._tag_index[tag_entry] = []
            if feature.feature_id not in self._tag_index[tag_entry]:
                self._tag_index[tag_entry].append(feature.feature_id)

        # Update lineage
        for upstream_id in feature.upstream_features:
            if upstream_id not in self._lineage_index:
                self._lineage_index[upstream_id] = []
            if feature.feature_id not in self._lineage_index[upstream_id]:
                self._lineage_index[upstream_id].append(feature.feature_id)

        logger.info("Feature registered: %s (v%d, category=%s)", feature.feature_id, feature.version, feature.category.value)
        return feature.feature_id

    def get(self, feature_id: str) -> Optional[FeatureEntry]:
        """Get a feature by ID."""
        return self._features.get(feature_id)

    def get_by_name(self, name: str) -> Optional[FeatureEntry]:
        """Get a feature by name."""
        feature_id = self._name_index.get(name)
        return self._features.get(feature_id) if feature_id else None

    # -- Versioning --

    def version(self, feature_id: str, new_version: Optional[int] = None) -> Optional[str]:
        """Create a new version of an existing feature.

        Returns the new version ID.
        """
        feature = self._features.get(feature_id)
        if feature is None:
            logger.warning("Feature not found for versioning: %s", feature_id)
            return None

        new_ver = new_version or feature.version + 1
        new_feature = FeatureEntry(
            name=feature.name,
            description=feature.description,
            category=feature.category,
            domain=feature.domain,
            formula=feature.formula,
            input_datasets=list(feature.input_datasets),
            frequency=feature.frequency,
            lookback_window=feature.lookback_window,
            required_columns=list(feature.required_columns),
            null_policy=feature.null_policy,
            outlier_policy=feature.outlier_policy,
            version=new_ver,
            owner=feature.owner,
            team=feature.team,
            upstream_features=list(feature.upstream_features),
            tags=dict(feature.tags),
        )
        new_id = self.register(new_feature)
        feature.latest_version_id = new_id
        feature.updated_at = datetime.utcnow()
        logger.info("Feature versioned: %s -> %s (v%d)", feature_id, new_id, new_ver)
        return new_id

    # -- Lineage --

    def lineage(self, feature_id: str) -> Dict[str, List[str]]:
        """Get the complete lineage (upstream + downstream) for a feature."""
        feature = self._features.get(feature_id)
        if feature is None:
            return {"upstream": [], "downstream": []}
        return {
            "upstream": feature.upstream_features,
            "downstream": self._lineage_index.get(feature_id, []),
            "datasets": feature.upstream_datasets,
        }

    # -- Querying --

    def list_by_category(self, category: FeatureCategory) -> List[FeatureEntry]:
        """List all features in a given category."""
        ids = self._category_index.get(category, [])
        return [self._features[fid] for fid in ids if fid in self._features]

    def list_by_tag(self, tag_key: str, tag_value: str) -> List[FeatureEntry]:
        """List features matching a specific tag."""
        tag_entry = f"{tag_key}:{tag_value}"
        ids = self._tag_index.get(tag_entry, [])
        return [self._features[fid] for fid in ids if fid in self._features]

    def search(self, query: str) -> List[FeatureEntry]:
        """Simple text search across feature names and descriptions."""
        query_lower = query.lower()
        results: List[FeatureEntry] = []
        for feature in self._features.values():
            if query_lower in feature.name.lower() or query_lower in feature.description.lower():
                results.append(feature)
        return results

    def list_all(self) -> List[FeatureEntry]:
        """List all registered features."""
        return list(self._features.values())

    def count(self) -> int:
        """Total number of registered features."""
        return len(self._features)
