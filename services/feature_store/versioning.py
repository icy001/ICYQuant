"""Feature Versioning — semantic version management for features.

Provides full version lifecycle: create, promote, rollback, and diff.
Ensures historical experiments remain reproducible by pinning
specific feature versions.

Usage::

    from services.feature_store import FeatureVersioning, FeatureVersion

    versioning = FeatureVersioning()
    versioning.create("ema20", "v1", definition={...})
    versioning.promote("ema20", "v2")  # make v2 the active version
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VersionStage(str, Enum):
    """Version promotion stage."""

    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


@dataclass
class FeatureVersion:
    """A single version of a feature.

    Attributes:
        feature_name: Feature identifier.
        version: Version string (e.g. "v1", "v2.1").
        stage: Current promotion stage.
        definition: Feature computation logic / parameters.
        changelog: Description of changes from previous version.
        parent_version: Version this was derived from, if any.
        created_at: Unix timestamp.
        promoted_at: Unix timestamp of last stage promotion.
        metadata: Arbitrary metadata.
    """

    feature_name: str
    version: str
    stage: VersionStage = VersionStage.EXPERIMENTAL
    definition: Dict[str, Any] = field(default_factory=dict)
    changelog: str = ""
    parent_version: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    promoted_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


class FeatureVersioning:
    """Manages the versioning lifecycle for features.

    Supports creation, promotion through stages, rollback, and diff.
    Each feature maintains its own version history.
    """

    # ---- 分组：初始化 ----

    def __init__(self) -> None:
        self._history: Dict[str, List[FeatureVersion]] = {}
        self._active: Dict[str, str] = {}  # feature_name -> active version

    # ---- 分组：版本创建 ----

    def create(
        self,
        feature_name: str,
        version: str,
        definition: Optional[Dict[str, Any]] = None,
        changelog: str = "",
        parent_version: Optional[str] = None,
    ) -> FeatureVersion:
        """Create a new feature version.

        Args:
            feature_name: Feature identifier.
            version: New version string.
            definition: Feature computation definition.
            changelog: Description of changes.
            parent_version: Version this derives from.

        Returns:
            The created FeatureVersion.

        Raises:
            ValueError: If version already exists.
        """
        if feature_name not in self._history:
            self._history[feature_name] = []

        existing = self._find(feature_name, version)
        if existing is not None:
            raise ValueError(
                f"Version '{version}' already exists for feature '{feature_name}'."
            )

        fv = FeatureVersion(
            feature_name=feature_name,
            version=version,
            definition=definition or {},
            changelog=changelog,
            parent_version=parent_version,
        )
        self._history[feature_name].append(fv)
        return fv

    # ---- 分组：版本晋升 ----

    def promote(
        self, feature_name: str, version: str, stage: VersionStage
    ) -> FeatureVersion:
        """Promote a version to a new stage.

        Args:
            feature_name: Feature identifier.
            version: Version to promote.
            stage: Target stage.

        Returns:
            The promoted FeatureVersion.

        Raises:
            KeyError: If feature or version not found.
        """
        fv = self._get(feature_name, version)
        old_stage = fv.stage

        # If promoting to ACTIVE, supersede previous active
        if stage == VersionStage.ACTIVE and old_stage != VersionStage.ACTIVE:
            prev_active = self._active.get(feature_name)
            if prev_active and prev_active != version:
                prev_fv = self._find(feature_name, prev_active)
                if prev_fv:
                    prev_fv.stage = VersionStage.SUPERSEDED

        fv.stage = stage
        fv.promoted_at = time.time()

        if stage == VersionStage.ACTIVE:
            self._active[feature_name] = version

        return fv

    def rollback(self, feature_name: str) -> Optional[FeatureVersion]:
        """Rollback to the most recent superseded version.

        Args:
            feature_name: Feature identifier.

        Returns:
            The rolled-back version, or None if no superseded version exists.
        """
        if feature_name not in self._history:
            return None

        superseded = [
            v
            for v in self._history[feature_name]
            if v.stage == VersionStage.SUPERSEDED
        ]
        if not superseded:
            return None

        superseded.sort(key=lambda v: (v.promoted_at, v.version), reverse=True)
        target = superseded[0]

        # Deactivate current active
        current_active = self._active.get(feature_name)
        if current_active:
            current_fv = self._find(feature_name, current_active)
            if current_fv:
                current_fv.stage = VersionStage.SUPERSEDED

        target.stage = VersionStage.ACTIVE
        target.promoted_at = time.time()
        self._active[feature_name] = target.version
        return target

    # ---- 分组：查询 ----

    def get_active(self, feature_name: str) -> Optional[FeatureVersion]:
        """Get the currently active version of a feature.

        Args:
            feature_name: Feature identifier.

        Returns:
            The active FeatureVersion, or None if no active version.
        """
        active_ver = self._active.get(feature_name)
        if active_ver is None:
            return None
        return self._find(feature_name, active_ver)

    def get(self, feature_name: str, version: str) -> FeatureVersion:
        """Get a specific version.

        Args:
            feature_name: Feature identifier.
            version: Version string.

        Returns:
            The FeatureVersion.

        Raises:
            KeyError: If not found.
        """
        return self._get(feature_name, version)

    def list_history(self, feature_name: str) -> List[FeatureVersion]:
        """List version history for a feature, newest first.

        Args:
            feature_name: Feature identifier.

        Returns:
            List of FeatureVersion.
        """
        if feature_name not in self._history:
            return []
        versions = list(self._history[feature_name])
        versions.sort(key=lambda v: (v.created_at, v.version), reverse=True)
        return versions

    def diff(
        self, feature_name: str, version_a: str, version_b: str
    ) -> Dict[str, Any]:
        """Compare two versions and return differences.

        Args:
            feature_name: Feature identifier.
            version_a: First version.
            version_b: Second version.

        Returns:
            Dict with 'added', 'removed', 'changed' keys.

        Raises:
            KeyError: If either version not found.
        """
        fv_a = self._get(feature_name, version_a)
        fv_b = self._get(feature_name, version_b)

        def_a = fv_a.definition
        def_b = fv_b.definition

        all_keys = set(def_a.keys()) | set(def_b.keys())
        added = {k: def_b[k] for k in all_keys if k not in def_a}
        removed = {k: def_a[k] for k in all_keys if k not in def_b}
        changed = {
            k: {"from": def_a[k], "to": def_b[k]}
            for k in all_keys
            if k in def_a and k in def_b and def_a[k] != def_b[k]
        }

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "changelog_a": fv_a.changelog,
            "changelog_b": fv_b.changelog,
        }

    # ---- 分组：内部 ----

    def _find(self, feature_name: str, version: str) -> Optional[FeatureVersion]:
        """Internal lookup by feature and version."""
        if feature_name not in self._history:
            return None
        for v in self._history[feature_name]:
            if v.version == version:
                return v
        return None

    def _get(self, feature_name: str, version: str) -> FeatureVersion:
        """Internal lookup, raises KeyError if not found."""
        fv = self._find(feature_name, version)
        if fv is None:
            if feature_name not in self._history:
                raise KeyError(f"Feature '{feature_name}' not found.")
            raise KeyError(f"Feature '{feature_name}' version '{version}' not found.")
        return fv
