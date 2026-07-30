"""ML Platform - AI Research & Machine Learning Foundation.

The ML Platform provides institutional-grade infrastructure for:
- Experiment Tracking: Record every training run with full reproducibility
- Model Registry: Manage model lifecycle (Development → Production → Archived)
- Artifact Storage: Persist models, reports, and training outputs
- Metadata Management: Track model lineage and provenance
- ML Runtime: Unified job execution (training, inference, batch, online)
- Training Scheduler: Automated periodic retraining

Usage::

    from services.ml import MLService

    service = MLService()
    exp = service.create_experiment(name="alpha_v18", framework="LightGBM")
    service.log_metrics(exp.id, {"sharpe": 2.03, "accuracy": 0.742})
    model = service.register_model("alpha_model", "v4", exp.id)
    service.promote_model("alpha_model", "v4", "Production")
"""

from __future__ import annotations

from services.ml.config import MLConfig
from services.ml.metadata import (
    ModelMetadata,
    MetadataManager,
    ModelFramework,
    ModelStage,
)
from services.ml.registry import (
    ModelRegistry,
    ModelVersion,
    ModelStage,
    RegistryEntry,
)
from services.ml.experiment import (
    ExperimentTracker,
    Experiment,
    ExperimentStatus,
    RunInfo,
)
from services.ml.artifact import (
    ArtifactManager,
    Artifact,
    ArtifactType,
)
from services.ml.service import MLService

__all__ = [
    # Service
    "MLService",
    "MLConfig",
    # Metadata
    "ModelMetadata",
    "MetadataManager",
    "ModelFramework",
    "ModelStage",
    # Registry
    "ModelRegistry",
    "ModelVersion",
    "RegistryEntry",
    # Experiment
    "ExperimentTracker",
    "Experiment",
    "ExperimentStatus",
    "RunInfo",
    # Artifact
    "ArtifactManager",
    "Artifact",
    "ArtifactType",
]
