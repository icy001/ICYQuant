"""
ICYQuant Model Registry - Central model management and lifecycle.

Model lifecycle stages:

    TRAINING
       ↓
    VALIDATED
       ↓
    CANDIDATE
       ↓
    STAGING
       ↓
    PRODUCTION
       ↓
    ARCHIVED

Each model binds: feature version, dataset version, training run,
model artifact, metrics, and code version.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model lifecycle stages."""

    TRAINING = "training"       # Currently training
    VALIDATED = "validated"     # Passed validation
    CANDIDATE = "candidate"     # Candidate for production
    STAGING = "staging"         # In staging/pre-production
    PRODUCTION = "production"   # Live in production
    ARCHIVED = "archived"       # Retired/archived
    DEPRECATED = "deprecated"   # Superseded by newer version
    REJECTED = "rejected"       # Failed review


@dataclass
class ModelEntry:
    """A model registered in the model registry."""

    model_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Type
    model_framework: str = "lightgbm"
    model_type: str = "regressor"     # regressor, classifier, ranker
    model_class: str = ""

    # Current version
    current_version: str = "v1"
    current_version_id: Optional[str] = None

    # Training info
    dataset_id: Optional[str] = None
    experiment_id: Optional[str] = None
    feature_ids: List[str] = field(default_factory=list)

    # Evaluation
    primary_metric: str = "ic"
    best_metric_value: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)

    # Status
    status: ModelStatus = ModelStatus.TRAINING

    # Ownership
    owner: str = ""
    team: str = ""

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Version history
    version_ids: List[str] = field(default_factory=list)


class ModelRegistry:
    """Central model registry for the platform.

    Manages the complete model lifecycle from training to production
    to archival. Integrates with model serving for deployment.
    """

    def __init__(self) -> None:
        self._models: Dict[str, ModelEntry] = {}
        self._name_index: Dict[str, str] = {}  # name -> model_id
        self._status_index: Dict[ModelStatus, List[str]] = {}

    # -- Registration --

    def register(self, model: ModelEntry) -> str:
        """Register a new model in the registry."""
        if model.name and model.name in self._name_index:
            existing_id = self._name_index[model.name]
            logger.warning("Model name '%s' already exists (%s), updating", model.name, existing_id)

        model.updated_at = datetime.utcnow()
        self._models[model.model_id] = model

        if model.name:
            self._name_index[model.name] = model.model_id

        # Update status index
        if model.status not in self._status_index:
            self._status_index[model.status] = []
        if model.model_id not in self._status_index[model.status]:
            self._status_index[model.status].append(model.model_id)

        logger.info("Model registered: %s (%s, status=%s)", model.model_id, model.name, model.status.value)
        return model.model_id

    def get(self, model_id: str) -> Optional[ModelEntry]:
        """Get a model by ID."""
        return self._models.get(model_id)

    def get_by_name(self, name: str) -> Optional[ModelEntry]:
        """Get a model by name."""
        model_id = self._name_index.get(name)
        return self._models.get(model_id) if model_id else None

    # -- Lifecycle Transitions --

    def transition(self, model_id: str, new_status: ModelStatus) -> bool:
        """Transition a model to a new lifecycle status.

        Valid transitions are enforced.
        """
        model = self._models.get(model_id)
        if model is None:
            logger.warning("Model not found: %s", model_id)
            return False

        valid_transitions = {
            ModelStatus.TRAINING: [ModelStatus.VALIDATED, ModelStatus.REJECTED],
            ModelStatus.VALIDATED: [ModelStatus.CANDIDATE, ModelStatus.REJECTED],
            ModelStatus.CANDIDATE: [ModelStatus.STAGING, ModelStatus.REJECTED],
            ModelStatus.STAGING: [ModelStatus.PRODUCTION, ModelStatus.REJECTED],
            ModelStatus.PRODUCTION: [ModelStatus.ARCHIVED, ModelStatus.DEPRECATED],
            ModelStatus.ARCHIVED: [ModelStatus.PRODUCTION],  # can restore
            ModelStatus.DEPRECATED: [ModelStatus.ARCHIVED],
            ModelStatus.REJECTED: [ModelStatus.TRAINING],
        }

        allowed = valid_transitions.get(model.status, [])
        if new_status not in allowed:
            logger.warning("Invalid transition: %s -> %s (allowed: %s)",
                           model.status.value, new_status.value,
                           [s.value for s in allowed])
            return False

        # Update status index
        if model.model_id in self._status_index.get(model.status, []):
            self._status_index[model.status].remove(model.model_id)

        model.status = new_status
        model.updated_at = datetime.utcnow()

        if new_status not in self._status_index:
            self._status_index[new_status] = []
        self._status_index[new_status].append(model.model_id)

        logger.info("Model %s transition: %s -> %s", model_id, model.status.name, new_status.name)
        return True

    # -- Queries --

    def list_by_status(self, status: ModelStatus) -> List[ModelEntry]:
        """List models by lifecycle status."""
        ids = self._status_index.get(status, [])
        return [self._models[mid] for mid in ids if mid in self._models]

    def get_production_models(self) -> List[ModelEntry]:
        """Get all production models."""
        return self.list_by_status(ModelStatus.PRODUCTION)

    def list_all(self) -> List[ModelEntry]:
        """List all registered models."""
        return list(self._models.values())

    def count(self) -> int:
        return len(self._models)

    def count_by_status(self) -> Dict[str, int]:
        """Count models per status."""
        counts: Dict[str, int] = {}
        for model in self._models.values():
            status_name = model.status.value
            counts[status_name] = counts.get(status_name, 0) + 1
        return counts
