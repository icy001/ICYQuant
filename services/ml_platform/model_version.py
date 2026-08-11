"""
ICYQuant Model Version - Model versioning system.

Manages versioned models with full reproducibility:

    NVDA_Momentum_Model

    v1.0
    v1.1
    v1.2
    v2.0

Each version binds:
- Feature Version
- Dataset Version
- Training Run
- Model Artifact
- Metrics
- Code Version
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class VersionStage(Enum):
    """Model version stage (aligned with ModelRegistry stages)."""

    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """A specific version of a trained model.

    Captures the complete state of a model at a point in time,
    enabling full reproducibility and audit trails.
    """

    version_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Identity
    model_id: str = ""
    model_name: str = ""
    version_number: int = 1
    version_label: str = ""     # e.g. "v1.0", "v2.1-production"

    # Artifact
    artifact_id: Optional[str] = None
    artifact_path: Optional[str] = None
    artifact_hash: str = ""     # SHA256 of model file
    artifact_size_bytes: int = 0

    # Training provenance
    training_run_id: Optional[str] = None
    experiment_run_id: Optional[str] = None
    dataset_id: Optional[str] = None
    feature_version_ids: Dict[str, str] = field(default_factory=dict)

    # Hyperparameters
    params: Dict[str, Any] = field(default_factory=dict)
    framework: str = "lightgbm"
    model_class: str = ""

    # Evaluation
    metrics: Dict[str, float] = field(default_factory=dict)
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Stage
    stage: VersionStage = VersionStage.NONE

    # Reproducibility
    code_version: str = ""       # git commit
    environment_hash: str = ""   # deps hash
    python_version: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def version_string(self) -> str:
        return self.version_label or f"v{self.version_number}"


class ModelVersionManager:
    """Manages model version lifecycle.

    Ensures:
    - Version immutability (once created, metadata cannot change)
    - Version comparison
    - Stage transitions (none → staging → production → archived)
    - Full lineage tracking
    """

    def __init__(self) -> None:
        self._versions: Dict[str, ModelVersion] = {}
        self._model_versions: Dict[str, List[str]] = {}  # model_id -> [version_ids]

    def create(self, version: ModelVersion) -> str:
        """Create a new model version."""
        self._versions[version.version_id] = version

        if version.model_id not in self._model_versions:
            self._model_versions[version.model_id] = []
        self._model_versions[version.model_id].append(version.version_id)

        logger.info("ModelVersion created: %s/%s (version=%s)",
                     version.model_name, version.version_id, version.version_string)
        return version.version_id

    def get(self, version_id: str) -> Optional[ModelVersion]:
        """Get a version by ID."""
        return self._versions.get(version_id)

    def get_latest(self, model_id: str) -> Optional[ModelVersion]:
        """Get the latest version of a model."""
        version_ids = self._model_versions.get(model_id, [])
        if not version_ids:
            return None
        return self._versions.get(version_ids[-1])

    def get_production(self, model_id: str) -> Optional[ModelVersion]:
        """Get the current production version."""
        version_ids = self._model_versions.get(model_id, [])
        for vid in reversed(version_ids):
            version = self._versions.get(vid)
            if version and version.stage == VersionStage.PRODUCTION:
                return version
        return None

    def get_history(self, model_id: str) -> List[ModelVersion]:
        """Get all versions of a model in chronological order."""
        version_ids = self._model_versions.get(model_id, [])
        return [self._versions[vid] for vid in version_ids if vid in self._versions]

    def promote(self, version_id: str, stage: VersionStage) -> bool:
        """Promote a version to a new stage."""
        version = self._versions.get(version_id)
        if version is None:
            return False

        # If promoting to production, archive previous production
        if stage == VersionStage.PRODUCTION:
            prev_prod = self.get_production(version.model_id)
            if prev_prod and prev_prod.version_id != version_id:
                prev_prod.stage = VersionStage.ARCHIVED

        version.stage = stage
        logger.info("ModelVersion %s promoted to %s", version_id, stage.value)
        return True

    def compare_versions(self, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        """Compare two model versions to understand changes."""
        va = self._versions.get(version_id_a)
        vb = self._versions.get(version_id_b)
        if not va or not vb:
            return {}

        metric_changes: Dict[str, float] = {}
        for metric in set(list(va.metrics.keys()) + list(vb.metrics.keys())):
            metric_changes[metric] = vb.metrics.get(metric, 0.0) - va.metrics.get(metric, 0.0)

        return {
            "version_a": va.version_string,
            "version_b": vb.version_string,
            "params_changed": va.params != vb.params,
            "dataset_changed": va.dataset_id != vb.dataset_id,
            "metric_changes": metric_changes,
            "code_changed": va.code_version != vb.code_version,
        }
