"""
ICYQuant Experiment Manager - Experiment lifecycle management.

Manages the full experiment lifecycle:
- Creating and configuring experiments
- Tracking experiment runs
- Comparing experiment results
- Managing experiment artifacts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment lifecycle stages."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment."""

    experiment_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Hypothesis
    hypothesis: str = ""

    # Data
    dataset_id: Optional[str] = None
    feature_ids: List[str] = field(default_factory=list)
    feature_view_id: Optional[str] = None

    # Model
    model_framework: str = "lightgbm"
    model_type: str = "regressor"
    params: Dict[str, Any] = field(default_factory=dict)

    # Training
    label_type: str = "regression"
    label_horizon: str = "5d"
    cv_folds: int = 5

    # Evaluation
    primary_metric: str = "ic"
    secondary_metrics: List[str] = field(default_factory=list)

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    parent_experiment_id: Optional[str] = None

    # Status
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ExperimentRun:
    """A single execution of an experiment."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    experiment_id: str = ""
    status: ExperimentStatus = ExperimentStatus.QUEUED

    # Results
    metrics: Dict[str, float] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    model_path: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)

    # Metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None


class ExperimentManager:
    """Manages the full experiment lifecycle.

    Provides:
    - Experiment configuration and creation
    - Run execution and tracking
    - Result comparison and analysis
    - Experiment lineage and dependencies
    """

    def __init__(self) -> None:
        self._experiments: Dict[str, ExperimentConfig] = {}
        self._runs: Dict[str, ExperimentRun] = {}
        self._experiment_runs: Dict[str, List[str]] = {}  # experiment_id -> [run_ids]

    # -- Create --

    def create_experiment(self, config: ExperimentConfig) -> str:
        """Create a new experiment."""
        self._experiments[config.experiment_id] = config
        self._experiment_runs[config.experiment_id] = []
        logger.info("Experiment created: %s (%s)", config.experiment_id, config.name)
        return config.experiment_id

    # -- Run --

    def start_run(self, experiment_id: str, params: Optional[Dict[str, Any]] = None) -> ExperimentRun:
        """Start a new experiment run."""
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        run = ExperimentRun(
            experiment_id=experiment_id,
            status=ExperimentStatus.RUNNING,
            params=params or {},
            started_at=datetime.utcnow(),
        )

        self._runs[run.run_id] = run
        self._experiment_runs[experiment_id].append(run.run_id)

        # Update experiment status
        self._experiments[experiment_id].status = ExperimentStatus.RUNNING
        self._experiments[experiment_id].started_at = run.started_at

        logger.info("Experiment run started: %s (experiment=%s)", run.run_id, experiment_id)
        return run

    def complete_run(self, run_id: str, metrics: Dict[str, float], artifacts: Optional[List[str]] = None) -> None:
        """Mark a run as completed with results."""
        run = self._runs.get(run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        run.status = ExperimentStatus.COMPLETED
        run.metrics = metrics
        run.artifacts = artifacts or []
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()

        # Update experiment
        experiment = self._experiments.get(run.experiment_id)
        if experiment:
            experiment.completed_at = run.completed_at
            experiment.status = ExperimentStatus.COMPLETED

        logger.info("Experiment run completed: %s (metrics=%s)", run_id, metrics)

    def fail_run(self, run_id: str, error: str) -> None:
        """Mark a run as failed."""
        run = self._runs.get(run_id)
        if run:
            run.status = ExperimentStatus.FAILED
            run.error = error
            run.completed_at = datetime.utcnow()

    # -- Query --

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentConfig]:
        return self._experiments.get(experiment_id)

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        return self._runs.get(run_id)

    def get_runs(self, experiment_id: str) -> List[ExperimentRun]:
        """Get all runs for an experiment."""
        run_ids = self._experiment_runs.get(experiment_id, [])
        return [self._runs[rid] for rid in run_ids if rid in self._runs]

    def get_best_run(self, experiment_id: str, metric: str = "ic") -> Optional[ExperimentRun]:
        """Get the best run by a metric."""
        runs = self.get_runs(experiment_id)
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        if not completed:
            return None
        return max(completed, key=lambda r: r.metrics.get(metric, float('-inf')))

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[ExperimentConfig]:
        """List experiments, optionally filtered by status."""
        exps = list(self._experiments.values())
        if status:
            exps = [e for e in exps if e.status == status]
        return sorted(exps, key=lambda e: e.created_at, reverse=True)

    # -- Compare --

    def compare_runs(self, run_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple experiment runs."""
        runs = [self._runs.get(rid) for rid in run_ids if rid in self._runs]
        if not runs:
            return {}

        comparison: Dict[str, Any] = {
            "run_ids": run_ids,
            "metrics": {},
        }

        if runs:
            all_metric_names = set()
            for run in runs:
                all_metric_names.update(run.metrics.keys())

            for metric in sorted(all_metric_names):
                comparison["metrics"][metric] = {
                    str(run.run_id): run.metrics.get(metric, float('nan'))
                    for run in runs
                }

        return comparison
