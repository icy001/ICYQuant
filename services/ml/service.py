"""ML Service - AI Research & Machine Learning Platform orchestrator.

The MLService is the central entry point for all ML operations, composing
the ExperimentTracker, ModelRegistry, MetadataManager, and ArtifactManager
into a unified API for the full ML lifecycle.

Lifecycle::

    Create Experiment → Start Run → Log Params/Metrics → Save Artifacts
    → Register Model → Promote to Production

Usage::

    from services.ml import MLService

    service = MLService()
    exp = service.create_experiment(name="alpha_v18", framework="LightGBM")
    run = service.start_run(exp.id)
    service.log_metrics(exp.id, run.run_id, {"sharpe": 2.03})
    service.finish_run(exp.id, run.run_id)
    model = service.register_model("alpha_model", "v4", exp.id)
    service.promote_model("alpha_model", "v4", ModelStage.PRODUCTION)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.ml.config import MLConfig
from services.ml.experiment import (
    ExperimentTracker,
    Experiment,
    ExperimentStatus,
    RunInfo,
)
from services.ml.registry import (
    ModelRegistry,
    ModelVersion,
    RegistryEntry,
)
from services.ml.metadata import (
    MetadataManager,
    ModelMetadata,
    ModelFramework,
    ModelStage,
)
from services.ml.artifact import (
    ArtifactManager,
    Artifact,
    ArtifactType,
)


class MLService:
    """Orchestrator for the ML Platform.

    Composes all ML sub-components into a unified service layer,
    providing a clean API for the complete model lifecycle.
    """

    def __init__(self, config: Optional[MLConfig] = None) -> None:
        self.config = config or MLConfig()
        self.tracker = ExperimentTracker()
        self.registry = ModelRegistry()
        self.metadata = MetadataManager()
        self.artifacts = ArtifactManager()

    # ---- Experiment Operations ----

    def create_experiment(
        self,
        name: str,
        framework: str = "",
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        dataset: str = "",
        features: int = 0,
    ) -> Experiment:
        """Create a new experiment."""
        return self.tracker.create_experiment(
            name=name,
            framework=framework or self.config.default_framework,
            description=description,
            tags=tags,
            dataset=dataset,
            features=features,
        )

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID."""
        return self.tracker.get_experiment(experiment_id)

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Experiment]:
        """List all experiments, optionally filtered."""
        return self.tracker.list_experiments(status=status)

    def search_experiments(
        self,
        name_contains: str = "",
        framework: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> List[Experiment]:
        """Search experiments with filters."""
        return self.tracker.search(name_contains=name_contains, framework=framework, tags=tags)

    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """Compare metrics across experiments."""
        return self.tracker.compare_experiments(experiment_ids)

    def finish_experiment(self, experiment_id: str, status: ExperimentStatus = ExperimentStatus.COMPLETED) -> bool:
        """Mark an experiment as finished."""
        return self.tracker.update_experiment_status(experiment_id, status) is not None

    # ---- Run Operations ----

    def start_run(self, experiment_id: str) -> Optional[RunInfo]:
        """Start a new run in an experiment."""
        return self.tracker.start_run(experiment_id)

    def finish_run(
        self,
        experiment_id: str,
        run_id: str,
        status: ExperimentStatus = ExperimentStatus.COMPLETED,
    ) -> bool:
        """Finish a run."""
        return self.tracker.finish_run(experiment_id, run_id, status)

    def log_param(self, experiment_id: str, run_id: str, key: str, value: Any) -> bool:
        """Log a single parameter."""
        return self.tracker.log_param(experiment_id, run_id, key, value)

    def log_params(self, experiment_id: str, run_id: str, params: Dict[str, Any]) -> bool:
        """Log multiple parameters."""
        return self.tracker.log_params(experiment_id, run_id, params)

    def log_metric(self, experiment_id: str, run_id: str, key: str, value: float) -> bool:
        """Log a single metric."""
        return self.tracker.log_metric(experiment_id, run_id, key, value)

    def log_metrics(self, experiment_id: str, run_id: str, metrics: Dict[str, float]) -> bool:
        """Log multiple metrics."""
        return self.tracker.log_metrics(experiment_id, run_id, metrics)

    # ---- Model Registry Operations ----

    def register_model(
        self,
        model_name: str,
        version: str,
        experiment_id: str = "",
        artifact_ids: Optional[List[str]] = None,
        author: str = "",
        framework: ModelFramework = ModelFramework.LIGHTGBM,
        dataset: str = "",
        features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> RegistryEntry:
        """Register a model version with full metadata.

        This creates a ModelMetadata entry and registers the model
        in the registry in a single operation.
        """
        meta = ModelMetadata(
            model_name=model_name,
            version=version,
            author=author,
            framework=framework,
            dataset=dataset,
            experiment_id=experiment_id,
            features=list(features or []),
            hyperparameters=dict(hyperparameters or {}),
            metrics=dict(metrics or {}),
            description=description,
            tags=dict(tags or {}),
        )
        self.metadata.save(meta)
        return self.registry.register(
            model_name=model_name,
            version=version,
            metadata=meta,
            experiment_id=experiment_id,
            artifact_ids=artifact_ids,
            metrics=metrics,
        )

    def get_model(self, model_name: str) -> Optional[RegistryEntry]:
        """Get a model registry entry."""
        return self.registry.get(model_name)

    def get_model_version(self, model_name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a model version."""
        mv = self.registry.get_version(model_name, version)
        if mv:
            return mv.to_dict()
        return None

    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models."""
        return [e.to_dict() for e in self.registry.list_models()]

    def promote_model(self, model_name: str, version: str, stage: ModelStage) -> bool:
        """Promote a model to a new stage."""
        self.metadata.update_stage(model_name, version, stage)
        return self.registry.promote(model_name, version, stage)

    def demote_model(self, model_name: str, version: str, stage: ModelStage) -> bool:
        """Demote a model version (rollback)."""
        return self.registry.demote(model_name, version, stage)

    def archive_model(self, model_name: str, version: str) -> bool:
        """Archive a model version."""
        return self.registry.archive(model_name, version)

    def get_production_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get the production version of a model."""
        mv = self.registry.get_production(model_name)
        return mv.to_dict() if mv else None

    # ---- Metadata Operations ----

    def get_model_metadata(self, model_name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a model version."""
        meta = self.metadata.get_by_name_version(model_name, version)
        return meta.to_dict() if meta else None

    def list_model_versions(self, model_name: str) -> List[Dict[str, Any]]:
        """List all metadata versions for a model."""
        return [m.to_dict() for m in self.metadata.list_by_model(model_name)]

    def list_models_by_stage(self, stage: ModelStage) -> List[Dict[str, Any]]:
        """List all models at a given stage."""
        return [m.to_dict() for m in self.metadata.list_by_stage(stage)]

    # ---- Artifact Operations ----

    def save_artifact(
        self,
        experiment_id: str,
        name: str,
        artifact_type: ArtifactType,
        data: bytes,
        format: str = "",
        run_id: str = "",
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        """Save an artifact."""
        return self.artifacts.save_artifact(
            experiment_id=experiment_id,
            name=name,
            artifact_type=artifact_type,
            data=data,
            format=format,
            run_id=run_id,
            tags=tags,
            metadata=metadata,
        )

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact by ID."""
        return self.artifacts.get_artifact(artifact_id)

    def list_experiment_artifacts(self, experiment_id: str) -> List[Dict[str, Any]]:
        """List all artifacts for an experiment."""
        return [a.to_dict() for a in self.artifacts.list_by_experiment(experiment_id)]

    # ---- Summary ----

    def get_status(self) -> Dict[str, Any]:
        """Get overall ML platform status."""
        return {
            "experiments": self.tracker.count(),
            "runs": self.tracker.run_count(),
            "models": self.registry.count(),
            "versions": self.registry.version_count(),
            "metadata_entries": self.metadata.count(),
            "artifacts": self.artifacts.count(),
            "artifacts_size_bytes": self.artifacts.total_size_bytes(),
            "production_models": len(self.registry.list_by_stage(ModelStage.PRODUCTION)),
            "config": self.config.to_dict(),
        }
