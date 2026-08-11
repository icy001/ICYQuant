"""
ICYQuant Feature Group - Logical grouping of related features.

Feature Groups organize features by domain, strategy, or pipeline.
They provide batch registration, joint validation, and collective
lineage tracking for groups of features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FeatureGroup:
    """A logical group of related features.

    Examples:
    - "momentum_factors": momentum_20d, momentum_60d, momentum_120d
    - "volatility_factors": volatility_20d, volatility_60d, garch_vol
    - "fundamental_signals": pe_ratio, pb_ratio, ev_ebitda, roe
    """

    group_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Members
    feature_ids: List[str] = field(default_factory=list)

    # Organization
    domain: str = ""        # equity, fixed_income, macro, crypto
    strategy: str = ""       # momentum, mean_reversion, value, etc.

    # Computation
    compute_priority: int = 0
    compute_schedule: str = "daily"  # daily, weekly, monthly, on_demand

    # Metadata
    owner: str = ""
    team: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deprecated: bool = False

    def add_feature(self, feature_id: str) -> None:
        """Add a feature to the group."""
        if feature_id not in self.feature_ids:
            self.feature_ids.append(feature_id)
            self.updated_at = datetime.utcnow()

    def remove_feature(self, feature_id: str) -> None:
        """Remove a feature from the group."""
        if feature_id in self.feature_ids:
            self.feature_ids.remove(feature_id)
            self.updated_at = datetime.utcnow()

    def contains(self, feature_id: str) -> bool:
        """Check if a feature belongs to this group."""
        return feature_id in self.feature_ids

    @property
    def size(self) -> int:
        return len(self.feature_ids)


class FeatureGroupManager:
    """Manages feature groups with indexing."""

    def __init__(self) -> None:
        self._groups: Dict[str, FeatureGroup] = {}
        self._feature_to_groups: Dict[str, List[str]] = {}

    def create(self, group: FeatureGroup) -> str:
        """Register a new feature group."""
        self._groups[group.group_id] = group
        for fid in group.feature_ids:
            if fid not in self._feature_to_groups:
                self._feature_to_groups[fid] = []
            if group.group_id not in self._feature_to_groups[fid]:
                self._feature_to_groups[fid].append(group.group_id)
        logger.info("FeatureGroup created: %s (%d features)", group.group_id, group.size)
        return group.group_id

    def get(self, group_id: str) -> Optional[FeatureGroup]:
        """Get a group by ID."""
        return self._groups.get(group_id)

    def get_groups_for_feature(self, feature_id: str) -> List[FeatureGroup]:
        """Get all groups containing a given feature."""
        group_ids = self._feature_to_groups.get(feature_id, [])
        return [self._groups[gid] for gid in group_ids if gid in self._groups]

    def list_all(self) -> List[FeatureGroup]:
        return list(self._groups.values())

    def delete(self, group_id: str) -> bool:
        """Delete a feature group."""
        group = self._groups.pop(group_id, None)
        if group:
            for fid in group.feature_ids:
                if fid in self._feature_to_groups:
                    self._feature_to_groups[fid] = [
                        g for g in self._feature_to_groups[fid] if g != group_id
                    ]
            return True
        return False
