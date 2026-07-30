"""Feature Registry — central registration for all features.

Manages the lifecycle of feature definitions: register, update,
deprecate, and query. Ensures every strategy and model uses the
same canonical feature definitions.

Usage::

    from services.feature_store import FeatureRegistry, FeatureDefinition

    registry = FeatureRegistry()
    registry.register(FeatureDefinition(
        feature_name="ema20",
        version="v1",
        owner="research",
        dtype="float64",
        frequency="1d",
        description="20-period exponential moving average",
    ))
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FeatureStatus(str, Enum):
    """Feature lifecycle status."""

    DRAFT = "draft"
    REGISTERED = "registered"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class FeatureDefinition:
    """Immutable feature definition.

    Attributes:
        feature_name: Unique feature identifier.
        version: Semantic version string (e.g. "v1", "v2.1").
        owner: Team or individual responsible.
        dtype: Expected data type (e.g. "float64", "int32", "bool").
        frequency: Data frequency (e.g. "1min", "1d", "1m").
        description: Human-readable description.
        category: Logical category for catalog grouping.
        tags: Searchable tags.
        source: Upstream data source identifier.
        status: Lifecycle status.
        metadata: Arbitrary key-value metadata.
        registered_at: Unix timestamp of registration.
        updated_at: Unix timestamp of last update.
    """

    feature_name: str
    version: str = "v1"
    owner: str = "research"
    dtype: str = "float64"
    frequency: str = "1d"
    description: str = ""
    category: str = "uncategorized"
    tags: List[str] = field(default_factory=list)
    source: str = ""
    status: FeatureStatus = FeatureStatus.DRAFT
    metadata: Dict[str, str] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class FeatureRegistry:
    """Central registry for all feature definitions.

    Provides CRUD operations and search over feature definitions,
    enforcing uniqueness of (feature_name, version) pairs.

    Lifecycle::

        DRAFT -> REGISTERED -> DEPRECATED -> RETIRED
    """

    # ---- 分组：初始化 ----

    def __init__(self) -> None:
        self._features: Dict[str, List[FeatureDefinition]] = {}

    # ---- 分组：注册 ----

    def register(self, definition: FeatureDefinition) -> FeatureDefinition:
        """Register a new feature definition.

        Args:
            definition: FeatureDefinition to register.

        Returns:
            The registered FeatureDefinition (status set to REGISTERED).

        Raises:
            ValueError: If (name, version) already exists.
        """
        if definition.feature_name not in self._features:
            self._features[definition.feature_name] = []

        existing = self._find_version(definition.feature_name, definition.version)
        if existing is not None:
            raise ValueError(
                f"Feature '{definition.feature_name}' version '{definition.version}' already registered."
            )

        definition.status = FeatureStatus.REGISTERED
        definition.registered_at = time.time()
        definition.updated_at = definition.registered_at
        self._features[definition.feature_name].append(definition)
        return definition

    def update(self, feature_name: str, version: str, **kwargs: Any) -> FeatureDefinition:
        """Update fields on an existing feature definition.

        Args:
            feature_name: Feature name.
            version: Version to update.
            **kwargs: Fields to update (owner, dtype, description, tags, etc.).

        Returns:
            The updated FeatureDefinition.

        Raises:
            KeyError: If feature or version not found.
        """
        entry = self.get(feature_name, version)
        for key, value in kwargs.items():
            if hasattr(entry, key) and key not in ("feature_name", "version", "registered_at"):
                setattr(entry, key, value)
        entry.updated_at = time.time()
        return entry

    def deprecate(self, feature_name: str, version: str) -> FeatureDefinition:
        """Mark a feature version as deprecated.

        Args:
            feature_name: Feature name.
            version: Version to deprecate.

        Returns:
            The updated FeatureDefinition.

        Raises:
            KeyError: If feature or version not found.
        """
        entry = self.get(feature_name, version)
        entry.status = FeatureStatus.DEPRECATED
        entry.updated_at = time.time()
        return entry

    def retire(self, feature_name: str, version: str) -> FeatureDefinition:
        """Mark a feature version as retired.

        Args:
            feature_name: Feature name.
            version: Version to retire.

        Returns:
            The updated FeatureDefinition.

        Raises:
            KeyError: If feature or version not found.
        """
        entry = self.get(feature_name, version)
        entry.status = FeatureStatus.RETIRED
        entry.updated_at = time.time()
        return entry

    # ---- 分组：查询 ----

    def get(self, feature_name: str, version: Optional[str] = None) -> FeatureDefinition:
        """Get a specific feature definition.

        Args:
            feature_name: Feature name.
            version: Version string. If None, returns latest REGISTERED version.

        Returns:
            The FeatureDefinition.

        Raises:
            KeyError: If feature or version not found.
        """
        if feature_name not in self._features:
            raise KeyError(f"Feature '{feature_name}' not found.")

        versions = self._features[feature_name]

        if version is not None:
            entry = self._find_version(feature_name, version)
            if entry is None:
                raise KeyError(f"Feature '{feature_name}' version '{version}' not found.")
            return entry

        # Return latest REGISTERED
        registered = [v for v in versions if v.status == FeatureStatus.REGISTERED]
        if not registered:
            # Fallback to latest by time
            versions_sorted = sorted(versions, key=lambda v: (v.registered_at, v.version), reverse=True)
            return versions_sorted[0]

        registered.sort(key=lambda v: (v.registered_at, v.version), reverse=True)
        return registered[0]

    def list_versions(self, feature_name: str) -> List[FeatureDefinition]:
        """List all versions of a feature, newest first.

        Args:
            feature_name: Feature name.

        Returns:
            List of FeatureDefinition, sorted by registration time descending.

        Raises:
            KeyError: If feature not found.
        """
        if feature_name not in self._features:
            raise KeyError(f"Feature '{feature_name}' not found.")
        versions = list(self._features[feature_name])
        versions.sort(key=lambda v: (v.registered_at, v.version), reverse=True)
        return versions

    def list_all(self) -> Dict[str, List[FeatureDefinition]]:
        """List all registered features.

        Returns:
            Dict mapping feature_name -> list of FeatureDefinition.
        """
        return dict(self._features)

    def list_active(self) -> List[FeatureDefinition]:
        """List all active (REGISTERED) feature versions.

        Returns:
            List of active FeatureDefinition.
        """
        result: List[FeatureDefinition] = []
        for versions in self._features.values():
            for v in versions:
                if v.status == FeatureStatus.REGISTERED:
                    result.append(v)
        return result

    def search(
        self,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        tag: Optional[str] = None,
        dtype: Optional[str] = None,
        status: Optional[FeatureStatus] = None,
    ) -> List[FeatureDefinition]:
        """Search features by criteria.

        Args:
            category: Filter by category.
            owner: Filter by owner.
            tag: Filter by tag.
            dtype: Filter by data type.
            status: Filter by lifecycle status.

        Returns:
            List of matching FeatureDefinition.
        """
        results: List[FeatureDefinition] = []
        for versions in self._features.values():
            for v in versions:
                if category is not None and v.category != category:
                    continue
                if owner is not None and v.owner != owner:
                    continue
                if tag is not None and tag not in v.tags:
                    continue
                if dtype is not None and v.dtype != dtype:
                    continue
                if status is not None and v.status != status:
                    continue
                results.append(v)
        results.sort(key=lambda v: (v.registered_at, v.feature_name), reverse=True)
        return results

    def exists(self, feature_name: str, version: str) -> bool:
        """Check if a feature version exists.

        Args:
            feature_name: Feature name.
            version: Version string.

        Returns:
            True if the feature version exists.
        """
        return self._find_version(feature_name, version) is not None

    def count(self) -> int:
        """Return total number of registered feature versions.

        Returns:
            Total count of feature versions across all features.
        """
        return sum(len(versions) for versions in self._features.values())

    def feature_names(self) -> List[str]:
        """Return list of all unique feature names.

        Returns:
            Sorted list of feature names.
        """
        return sorted(self._features.keys())

    # ---- 分组：内部 ----

    def _find_version(self, feature_name: str, version: str) -> Optional[FeatureDefinition]:
        """Find a specific version within a feature's version list."""
        if feature_name not in self._features:
            return None
        for v in self._features[feature_name]:
            if v.version == version:
                return v
        return None
