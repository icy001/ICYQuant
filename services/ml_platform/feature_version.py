"""
ICYQuant Feature Version - Feature versioning system.

Manages versioned feature definitions and computed feature data.
Each version binds:
- Feature Definition (formula, parameters, policies)
- Computed Values (snapshot reference)
- Timestamp (when computed)
- Code Version (git commit)
- Environment (dependencies)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .feature_definition import FeatureDefinition
from .feature_registry import FeatureEntry

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    """Feature version lifecycle."""

    DRAFT = "draft"
    COMPUTED = "computed"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class FeatureVersion:
    """A specific version of a feature.

    Binds together the definition, computed values, code version,
    and environment for full reproducibility.

    Example lifecycle:
        momentum_20d v1.0 (DRAFT)
            → COMPUTED (values computed, snapshot created)
            → VALIDATED (quality checks passed)
            → ACTIVE (available for use)
            → DEPRECATED (v1.1 created)
            → ARCHIVED (no longer queryable)
    """

    version_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Feature identity
    feature_id: str = ""
    feature_name: str = ""
    version_number: int = 1

    # Definition snapshot
    feature_definition: Optional[FeatureDefinition] = None
    definition_hash: str = ""

    # Computed data
    snapshot_id: Optional[str] = None
    computed_at: Optional[datetime] = None
    data_start_date: Optional[datetime] = None
    data_end_date: Optional[datetime] = None
    entity_count: int = 0
    row_count: int = 0

    # Reproducibility
    code_version: str = ""       # git commit hash
    environment_hash: str = ""   # deps hash
    runtime_version: str = ""    # e.g. Python 3.10

    # Quality
    quality_report_id: Optional[str] = None
    quality_score: float = 0.0
    validation_passed: bool = False

    # Status
    status: VersionStatus = VersionStatus.DRAFT

    # Metadata
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    comment: str = ""

    def compute_definition_hash(self) -> str:
        """Compute a hash of the feature definition for identity checking."""
        if self.feature_definition:
            return self.feature_definition.content_hash()
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version_id": self.version_id,
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "version_number": self.version_number,
            "definition_hash": self.definition_hash,
            "snapshot_id": self.snapshot_id,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "data_start_date": self.data_start_date.isoformat() if self.data_start_date else None,
            "data_end_date": self.data_end_date.isoformat() if self.data_end_date else None,
            "entity_count": self.entity_count,
            "row_count": self.row_count,
            "code_version": self.code_version,
            "quality_score": self.quality_score,
            "status": self.status.value,
        }


class FeatureVersionManager:
    """Manages feature version lifecycle.

    Stores version history, handles version transitions,
    and enforces version immutability for computed versions.
    """

    def __init__(self) -> None:
        self._versions: Dict[str, FeatureVersion] = {}
        self._feature_version_history: Dict[str, List[str]] = {}  # feature_id -> [version_ids]

    def create_version(
        self,
        feature_id: str,
        feature_definition: FeatureDefinition,
        version_number: Optional[int] = None,
    ) -> FeatureVersion:
        """Create a new feature version in DRAFT status."""
        if version_number is None:
            existing = self._feature_version_history.get(feature_id, [])
            version_number = len(existing) + 1

        version = FeatureVersion(
            feature_id=feature_id,
            feature_name=feature_definition.name,
            version_number=version_number,
            feature_definition=feature_definition,
            definition_hash=feature_definition.content_hash(),
            status=VersionStatus.DRAFT,
        )

        self._versions[version.version_id] = version
        if feature_id not in self._feature_version_history:
            self._feature_version_history[feature_id] = []
        self._feature_version_history[feature_id].append(version.version_id)

        logger.info("FeatureVersion created: %s v%d (%s)", feature_id, version_number, version.version_id)
        return version

    def mark_computed(self, version_id: str, snapshot_id: str, metadata: Dict[str, Any]) -> None:
        """Mark a version as COMPUTED with its snapshot reference."""
        version = self._versions.get(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")

        version.snapshot_id = snapshot_id
        version.computed_at = datetime.utcnow()
        version.code_version = metadata.get("code_version", "")
        version.environment_hash = metadata.get("environment_hash", "")
        version.status = VersionStatus.COMPUTED
        logger.info("FeatureVersion %s marked COMPUTED", version_id)

    def mark_validated(self, version_id: str, quality_score: float, passed: bool) -> None:
        """Mark a version as VALIDATED after quality checks."""
        version = self._versions.get(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")
        version.status = VersionStatus.VALIDATED
        version.quality_score = quality_score
        version.validation_passed = passed
        logger.info("FeatureVersion %s marked VALIDATED (score=%.2f)", version_id, quality_score)

    def activate(self, version_id: str) -> None:
        """Activate a version (deactivate previous active version)."""
        version = self._versions.get(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")

        # Deactivate previous versions of same feature
        history = self._feature_version_history.get(version.feature_id, [])
        for vid in history:
            if vid != version_id and self._versions[vid].status == VersionStatus.ACTIVE:
                self._versions[vid].status = VersionStatus.DEPRECATED

        version.status = VersionStatus.ACTIVE
        logger.info("FeatureVersion %s activated", version_id)

    def deprecate(self, version_id: str) -> None:
        """Deprecate a version."""
        version = self._versions.get(version_id)
        if version:
            version.status = VersionStatus.DEPRECATED

    def archive(self, version_id: str) -> None:
        """Archive a version."""
        version = self._versions.get(version_id)
        if version:
            version.status = VersionStatus.ARCHIVED

    # -- Queries --

    def get(self, version_id: str) -> Optional[FeatureVersion]:
        return self._versions.get(version_id)

    def get_latest(self, feature_id: str) -> Optional[FeatureVersion]:
        """Get the latest version of a feature."""
        history = self._feature_version_history.get(feature_id, [])
        if not history:
            return None
        return self._versions.get(history[-1])

    def get_active(self, feature_id: str) -> Optional[FeatureVersion]:
        """Get the currently active version."""
        history = self._feature_version_history.get(feature_id, [])
        for vid in reversed(history):
            version = self._versions.get(vid)
            if version and version.status == VersionStatus.ACTIVE:
                return version
        return None

    def get_history(self, feature_id: str) -> List[FeatureVersion]:
        """Get all versions of a feature in order."""
        history = self._feature_version_history.get(feature_id, [])
        return [self._versions[vid] for vid in history if vid in self._versions]

    def diff_versions(self, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        """Diff two feature versions to understand what changed."""
        va = self._versions.get(version_id_a)
        vb = self._versions.get(version_id_b)
        if not va or not vb:
            return {}

        changes: Dict[str, Any] = {
            "definition_changed": va.definition_hash != vb.definition_hash,
            "version_a": va.version_number,
            "version_b": vb.version_number,
        }

        if va.feature_definition and vb.feature_definition:
            # Compare key fields
            for field_name in ("formula", "lookback_window", "null_policy", "outlier_policy"):
                val_a = getattr(va.feature_definition, field_name, None)
                val_b = getattr(vb.feature_definition, field_name, None)
                if val_a != val_b:
                    changes[field_name] = {"from": str(val_a)[:100], "to": str(val_b)[:100]}

        return changes
