"""
ICYQuant Feature View - Logical view combining features from multiple groups.

A Feature View defines a specific "view" over the feature store that
combines features from potentially different groups and serves as the
input specification for training datasets or inference pipelines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .feature_registry import FeatureFrequency

logger = logging.getLogger(__name__)


@dataclass
class FeatureViewConfig:
    """Configuration for a feature view."""

    # Feature selection
    feature_ids: List[str] = field(default_factory=list)
    feature_group_ids: List[str] = field(default_factory=list)

    # Time alignment
    timestamp_column: str = "trade_date"
    entity_column: str = "symbol"

    # Filtering
    universe_filter: Optional[str] = None  # e.g. "sector == 'Technology'"
    universe_ids: List[str] = field(default_factory=list)

    # Window
    lookback_days: int = 252
    min_history_days: int = 60

    # Output
    output_format: str = "pandas"  # pandas, numpy, arrow


@dataclass
class FeatureView:
    """A logical view over the feature store.

    Combines features from multiple groups into a single view that can
    be queried for point-in-time feature retrieval. Serves as the
    standard interface between feature storage and model consumption.
    """

    view_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Config
    config: FeatureViewConfig = field(default_factory=FeatureViewConfig)

    # Resolved state (computed at init/refresh time)
    resolved_feature_ids: List[str] = field(default_factory=list)
    resolved_feature_versions: Dict[str, int] = field(default_factory=dict)

    # Metadata
    version: int = 1
    owner: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_materialized: Optional[datetime] = None

    # Consistency information
    feature_frequencies: Dict[FeatureFrequency, List[str]] = field(default_factory=dict)

    @property
    def feature_count(self) -> int:
        return len(self.resolved_feature_ids)

    def add_feature(self, feature_id: str, version: int = 1) -> None:
        """Add a feature to this view."""
        if feature_id not in self.config.feature_ids:
            self.config.feature_ids.append(feature_id)
        self.resolved_feature_versions[feature_id] = version
        self.updated_at = datetime.utcnow()

    def add_group(self, group_id: str) -> None:
        """Add all features from a group to this view."""
        if group_id not in self.config.feature_group_ids:
            self.config.feature_group_ids.append(group_id)
            self.updated_at = datetime.utcnow()

    def set_universe(self, universe_ids: List[str]) -> None:
        """Set the universe of entities for this view."""
        self.config.universe_ids = list(universe_ids)
        self.updated_at = datetime.utcnow()


class FeatureViewManager:
    """Manages feature views."""

    def __init__(self) -> None:
        self._views: Dict[str, FeatureView] = {}
        self._name_index: Dict[str, str] = {}

    def create(self, view: FeatureView) -> str:
        """Create/register a feature view."""
        if view.name and view.name in self._name_index:
            existing = self._name_index[view.name]
            logger.warning("FeatureView name '%s' exists (%s), overwriting", view.name, existing)

        self._views[view.view_id] = view
        if view.name:
            self._name_index[view.name] = view.view_id
        logger.info("FeatureView created: %s (%d features)", view.view_id, view.feature_count)
        return view.view_id

    def get(self, view_id: str) -> Optional[FeatureView]:
        return self._views.get(view_id)

    def get_by_name(self, name: str) -> Optional[FeatureView]:
        view_id = self._name_index.get(name)
        return self._views.get(view_id) if view_id else None

    def list_all(self) -> List[FeatureView]:
        return list(self._views.values())

    def build_training_view(
        self,
        name: str,
        feature_ids: List[str],
        lookback_days: int = 252,
        **kwargs: Any,
    ) -> FeatureView:
        """Create a view suitable for training dataset building."""
        config = FeatureViewConfig(
            feature_ids=list(feature_ids),
            lookback_days=lookback_days,
            **kwargs,
        )
        view = FeatureView(name=name, config=config)
        view.resolved_feature_ids = list(feature_ids)
        self.create(view)
        return view

    def build_inference_view(
        self,
        name: str,
        feature_ids: List[str],
        **kwargs: Any,
    ) -> FeatureView:
        """Create a view suitable for online inference."""
        config = FeatureViewConfig(
            feature_ids=list(feature_ids),
            lookback_days=1,  # minimal for inference
            **kwargs,
        )
        view = FeatureView(name=name, config=config)
        view.resolved_feature_ids = list(feature_ids)
        self.create(view)
        return view
