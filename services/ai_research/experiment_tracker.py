"""
ICYQuant Experiment Tracker — ML experiment tracking for quantitative research.

Tracks experiment parameters, metrics, artifacts, and versions for
reproducible machine learning research in quantitative finance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Experiment:
    """A single ML experiment."""
    experiment_id: str
    name: str
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.CREATED
    session_id: str = ""
    notebook_id: str = ""

    # Parameters
    parameters: dict[str, Any] = field(default_factory=dict)

    # Metrics over time
    metrics: list[dict[str, Any]] = field(default_factory=list)

    # Best metrics
    best_metrics: dict[str, Any] = field(default_factory=dict)

    # Artifacts (model files, charts, etc.)
    artifact_ids: list[str] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Versioning
    version: int = 1
    parent_experiment_id: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExperimentTracker:
    """ML experiment tracking for reproducible quantitative research.

    Responsibilities:
        - Create and manage experiments
        - Log parameters and hyperparameters
        - Track metrics across training steps
        - Record best metrics
        - Link artifacts (models, charts, reports)
        - Version experiments for lineage tracking
    """

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}
        self._total_created = 0

    def create(
        self,
        name: str,
        description: str = "",
        parameters: Optional[dict[str, Any]] = None,
        session_id: str = "",
        notebook_id: str = "",
        tags: Optional[list[str]] = None,
    ) -> Experiment:
        """Create a new experiment."""
        import uuid
        experiment = Experiment(
            experiment_id=str(uuid.uuid4()),
            name=name,
            description=description,
            parameters=parameters or {},
            session_id=session_id,
            notebook_id=notebook_id,
            tags=tags or [],
        )
        self._experiments[experiment.experiment_id] = experiment
        self._total_created += 1
        logger.info("Created experiment: %s", experiment.experiment_id)
        return experiment

    def start(self, experiment_id: str) -> bool:
        """Mark an experiment as running."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return False
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(timezone.utc)
        return True

    def log_metrics(
        self,
        experiment_id: str,
        metrics: dict[str, Any],
        step: Optional[int] = None,
    ) -> bool:
        """Log metrics for an experiment step."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return False

        entry = {
            "step": step or len(experiment.metrics),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metrics,
        }
        experiment.metrics.append(entry)

        # Update best metrics
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                current_best = experiment.best_metrics.get(key)
                if current_best is None or value > current_best:
                    experiment.best_metrics[key] = value

        return True

    def log_artifact(self, experiment_id: str, artifact_id: str) -> bool:
        """Link an artifact to an experiment."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return False
        experiment.artifact_ids.append(artifact_id)
        return True

    def complete(self, experiment_id: str) -> bool:
        """Mark an experiment as completed."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return False
        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now(timezone.utc)
        if experiment.started_at:
            experiment.duration_seconds = (
                experiment.completed_at - experiment.started_at
            ).total_seconds()
        return True

    def fail(self, experiment_id: str, error: str = "") -> bool:
        """Mark an experiment as failed."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return False
        experiment.status = ExperimentStatus.FAILED
        experiment.metadata["error"] = error
        experiment.completed_at = datetime.now(timezone.utc)
        return True

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        return self._experiments.get(experiment_id)

    def list_by_session(self, session_id: str) -> list[Experiment]:
        """List experiments for a research session."""
        return [e for e in self._experiments.values() if e.session_id == session_id]

    def list_by_tag(self, tag: str) -> list[Experiment]:
        """List experiments by tag."""
        return [e for e in self._experiments.values() if tag in e.tags]

    def compare(
        self,
        experiment_ids: list[str],
    ) -> dict[str, Any]:
        """Compare metrics across experiments."""
        comparison: dict[str, Any] = {"experiments": [], "metrics": {}}
        for eid in experiment_ids:
            exp = self._experiments.get(eid)
            if exp:
                comparison["experiments"].append({
                    "id": exp.experiment_id,
                    "name": exp.name,
                    "best_metrics": exp.best_metrics,
                    "status": exp.status.value,
                })
                for key, value in exp.best_metrics.items():
                    if key not in comparison["metrics"]:
                        comparison["metrics"][key] = {}
                    comparison["metrics"][key][exp.name] = value
        return comparison

    def get_summary(self, experiment_id: str) -> Optional[dict[str, Any]]:
        """Get experiment summary."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return None

        return {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "parameter_count": len(experiment.parameters),
            "metric_steps": len(experiment.metrics),
            "best_metrics": experiment.best_metrics,
            "artifact_count": len(experiment.artifact_ids),
            "duration_seconds": experiment.duration_seconds,
            "tags": experiment.tags,
        }

    @property
    def experiment_count(self) -> int:
        return len(self._experiments)

    @property
    def total_created(self) -> int:
        return self._total_created
