"""Experiment Tracking - Record every training run with full reproducibility.

Tracks parameter, metric, artifact, and lineage information for each experiment,
ensuring full reproducibility of ML research.

Usage::

    tracker = ExperimentTracker()
    exp = tracker.create_experiment(name="alpha_v18", framework="LightGBM")
    tracker.log_params(exp.id, {"learning_rate": 0.05})
    tracker.log_metrics(exp.id, {"sharpe": 2.03, "accuracy": 0.742})
    tracker.finish_experiment(exp.id, status=ExperimentStatus.COMPLETED)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import uuid


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status."""

    CREATED = "Created"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class RunInfo:
    """Information about a single experiment run.

    Attributes:
        run_id: Unique run identifier within an experiment.
        started_at: ISO 8601 start timestamp.
        finished_at: ISO 8601 finish timestamp (None if still running).
        status: Current run status.
        params: Hyperparameters used in this run.
        metrics: Metrics collected during this run.
        tags: Arbitrary key-value tags.
        git_commit: Git commit hash.
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    finished_at: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.CREATED
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    git_commit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status.value,
            "params": dict(self.params),
            "metrics": dict(self.metrics),
            "tags": dict(self.tags),
            "git_commit": self.git_commit,
        }

    def add_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """Add or update a metric."""
        self.metrics[key] = value

    def add_param(self, key: str, value: Any) -> None:
        """Add or update a parameter."""
        self.params[key] = value


@dataclass
class Experiment:
    """A single machine learning experiment.

    Attributes:
        id: Unique experiment identifier.
        name: Human-readable experiment name.
        framework: ML framework used.
        description: Description of the experiment.
        status: Current experiment status.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
        tags: Arbitrary key-value tags.
        dataset: Training dataset identifier.
        features: Number of features.
        runs: Ordered list of runs.
        common_params: Parameters shared across all runs.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    framework: str = "LightGBM"
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.CREATED
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tags: Dict[str, str] = field(default_factory=dict)
    dataset: str = ""
    features: int = 0
    runs: List[RunInfo] = field(default_factory=list)
    common_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "framework": self.framework,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": dict(self.tags),
            "dataset": self.dataset,
            "features": self.features,
            "runs": [r.to_dict() for r in self.runs],
            "common_params": dict(self.common_params),
        }

    def get_latest_run(self) -> Optional[RunInfo]:
        """Get the most recent run."""
        return self.runs[-1] if self.runs else None

    def get_best_run(self, metric: str, maximize: bool = True) -> Optional[RunInfo]:
        """Get the run with the best value for a given metric."""
        if not self.runs:
            return None
        if maximize:
            return max(self.runs, key=lambda r: r.metrics.get(metric, float("-inf")))
        else:
            return min(self.runs, key=lambda r: r.metrics.get(metric, float("inf")))


class ExperimentTracker:
    """Tracks ML experiments with full reproducibility.

    Records experiments, runs, parameters, and metrics.
    Supports searching, filtering, and comparing experiments.

    Usage::

        tracker = ExperimentTracker()
        exp = tracker.create_experiment("alpha_v18", "LightGBM")
        run = tracker.start_run(exp.id)
        tracker.log_metric(exp.id, run.run_id, "sharpe", 2.03)
        tracker.finish_run(exp.id, run.run_id)
    """

    def __init__(self) -> None:
        self._experiments: Dict[str, Experiment] = {}

    # ---- Experiment CRUD ----

    def create_experiment(
        self,
        name: str,
        framework: str = "LightGBM",
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        dataset: str = "",
        features: int = 0,
    ) -> Experiment:
        """Create a new experiment.

        Args:
            name: Experiment name.
            framework: ML framework.
            description: Description.
            tags: Key-value tags.
            dataset: Training dataset identifier.
            features: Number of features.

        Returns:
            The created Experiment.
        """
        exp = Experiment(
            name=name,
            framework=framework,
            description=description,
            tags=dict(tags or {}),
            dataset=dataset,
            features=features,
        )
        self._experiments[exp.id] = exp
        return exp

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Experiment]:
        """List all experiments, optionally filtered by status."""
        exps = list(self._experiments.values())
        if status:
            exps = [e for e in exps if e.status == status]
        exps.sort(key=lambda e: (e.created_at, e.name), reverse=True)
        return exps

    def update_experiment_status(self, experiment_id: str, status: ExperimentStatus) -> Optional[Experiment]:
        """Update the status of an experiment."""
        exp = self._experiments.get(experiment_id)
        if exp:
            exp.status = status
            exp.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return exp

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment."""
        return self._experiments.pop(experiment_id, None) is not None

    # ---- Run Management ----

    def start_run(self, experiment_id: str) -> Optional[RunInfo]:
        """Start a new run within an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None
        run = RunInfo(status=ExperimentStatus.RUNNING)
        exp.runs.append(run)
        exp.status = ExperimentStatus.RUNNING
        exp.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return run

    def finish_run(self, experiment_id: str, run_id: str, status: ExperimentStatus = ExperimentStatus.COMPLETED) -> bool:
        """Finish a run with a given status."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        for run in exp.runs:
            if run.run_id == run_id:
                run.status = status
                run.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                exp.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return True
        return False

    def get_run(self, experiment_id: str, run_id: str) -> Optional[RunInfo]:
        """Get a specific run."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None
        for run in exp.runs:
            if run.run_id == run_id:
                return run
        return None

    # ---- Logging ----

    def log_param(self, experiment_id: str, run_id: str, key: str, value: Any) -> bool:
        """Log a parameter for a run."""
        run = self.get_run(experiment_id, run_id)
        if not run:
            return False
        run.add_param(key, value)
        return True

    def log_params(self, experiment_id: str, run_id: str, params: Dict[str, Any]) -> bool:
        """Log multiple parameters for a run."""
        run = self.get_run(experiment_id, run_id)
        if not run:
            return False
        for k, v in params.items():
            run.add_param(k, v)
        return True

    def log_metric(self, experiment_id: str, run_id: str, key: str, value: float) -> bool:
        """Log a metric for a run."""
        run = self.get_run(experiment_id, run_id)
        if not run:
            return False
        run.add_metric(key, value)
        return True

    def log_metrics(self, experiment_id: str, run_id: str, metrics: Dict[str, float]) -> bool:
        """Log multiple metrics for a run."""
        run = self.get_run(experiment_id, run_id)
        if not run:
            return False
        for k, v in metrics.items():
            run.add_metric(k, v)
        return True

    def log_common_params(self, experiment_id: str, params: Dict[str, Any]) -> bool:
        """Set parameters shared across all runs of an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        exp.common_params.update(params)
        return True

    def set_tags(self, experiment_id: str, tags: Dict[str, str]) -> bool:
        """Set tags for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        exp.tags.update(tags)
        return True

    # ---- Search & Compare ----

    def search(self, name_contains: str = "", framework: str = "", tags: Optional[Dict[str, str]] = None) -> List[Experiment]:
        """Search experiments by name, framework, or tags."""
        results = []
        for exp in self._experiments.values():
            if name_contains and name_contains.lower() not in exp.name.lower():
                continue
            if framework and framework.lower() != exp.framework.lower():
                continue
            if tags:
                if not all(exp.tags.get(k) == v for k, v in tags.items()):
                    continue
            results.append(exp)
        results.sort(key=lambda e: (e.created_at, e.name), reverse=True)
        return results

    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """Compare metrics across multiple experiments.

        Returns a summary with the latest run metrics from each experiment.
        """
        comparison: Dict[str, Any] = {}
        for eid in experiment_ids:
            exp = self._experiments.get(eid)
            if exp:
                latest = exp.get_latest_run()
                comparison[exp.name] = {
                    "id": exp.id,
                    "framework": exp.framework,
                    "dataset": exp.dataset,
                    "features": exp.features,
                    "status": exp.status.value,
                    "runs": len(exp.runs),
                    "latest_metrics": latest.metrics if latest else {},
                }
        return comparison

    def count(self) -> int:
        """Total number of experiments."""
        return len(self._experiments)

    def run_count(self) -> int:
        """Total number of runs across all experiments."""
        return sum(len(e.runs) for e in self._experiments.values())
