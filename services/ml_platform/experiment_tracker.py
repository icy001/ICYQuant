"""
ICYQuant Experiment Tracker - Detailed experiment run tracking.

    Every experiment records:

    Experiment
       │
       ├── Dataset
       ├── Features
       ├── Parameters
       ├── Model
       ├── Metrics
       ├── Artifacts
       └── Code Version

Example:
    Experiment #1042
    Model: LightGBM
    Features: 42
    IC: 0.071
    Rank IC: 0.094
    Sharpe: 1.82
    Max Drawdown: -8.7%
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExperimentRecord:
    """Complete record of a single experiment run.

    Captures everything needed to reproduce or audit the experiment:
    - What data was used (dataset + features)
    - What model was trained (framework + params)
    - What results were obtained (metrics)
    - What code/environment was used
    """

    experiment_id: str = field(default_factory=lambda: uuid4().hex[:12])
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""

    # Data
    dataset_id: Optional[str] = None
    feature_ids: List[str] = field(default_factory=list)
    feature_count: int = 0
    entity_ids: List[str] = field(default_factory=list)
    entity_count: int = 0
    train_row_count: int = 0
    test_row_count: int = 0

    # Time
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None

    # Model
    model_framework: str = "lightgbm"
    model_type: str = "regressor"
    model_params: Dict[str, Any] = field(default_factory=dict)
    model_class: str = ""

    # Training
    label_type: str = "regression"
    label_horizon: str = "5d"
    cv_folds: int = 5
    cv_method: str = "purged_kfold"

    # Results
    metrics: Dict[str, float] = field(default_factory=dict)
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Artifacts
    model_path: Optional[str] = None
    artifact_paths: List[str] = field(default_factory=list)
    plots: List[str] = field(default_factory=list)

    # Reproducibility
    code_version: str = ""       # git commit
    code_branch: str = ""
    environment_hash: str = ""   # deps hash
    python_version: str = ""

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    status: str = "completed"    # completed, failed, cancelled
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    def compute_hash(self) -> str:
        """Compute a reproducible experiment hash."""
        content = {
            "feature_ids": sorted(self.feature_ids),
            "model_framework": self.model_framework,
            "model_params": json.dumps(self.model_params, sort_keys=True),
            "label_type": self.label_type,
            "label_horizon": self.label_horizon,
            "cv_folds": self.cv_folds,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]

    def to_summary(self) -> Dict[str, Any]:
        """Generate a human-readable experiment summary."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "model": self.model_framework,
            "features": self.feature_count,
            "entities": self.entity_count,
            "train_rows": self.train_row_count,
            "test_rows": self.test_row_count,
            **self.metrics,
        }


class ExperimentTracker:
    """Records and tracks all experiment runs.

    Maintains a searchable history of experiments for:
    - Reproducing past results
    - Comparing experiment configurations
    - Tracking model improvement over time
    - Auditing model development process
    """

    def __init__(self) -> None:
        self._records: Dict[str, ExperimentRecord] = {}
        self._experiment_records: Dict[str, List[str]] = {}  # exp_id -> [run_ids]
        self._tag_index: Dict[str, List[str]] = {}

    # -- Record --

    def record(self, record: ExperimentRecord) -> str:
        """Record an experiment run."""
        self._records[record.run_id] = record

        exp_id = record.experiment_id
        if exp_id not in self._experiment_records:
            self._experiment_records[exp_id] = []
        self._experiment_records[exp_id].append(record.run_id)

        # Index by tags
        for tag_key, tag_val in record.tags.items():
            tag_entry = f"{tag_key}:{tag_val}"
            if tag_entry not in self._tag_index:
                self._tag_index[tag_entry] = []
            self._tag_index[tag_entry].append(record.run_id)

        logger.info("Experiment recorded: %s/%s (%s, IC=%.4f)",
                     exp_id, record.run_id, record.model_framework,
                     record.metrics.get("ic", 0.0))
        return record.run_id

    # -- Query --

    def get(self, run_id: str) -> Optional[ExperimentRecord]:
        """Get an experiment record by run ID."""
        return self._records.get(run_id)

    def get_experiment_runs(self, experiment_id: str) -> List[ExperimentRecord]:
        """Get all runs for an experiment."""
        run_ids = self._experiment_records.get(experiment_id, [])
        return [self._records[rid] for rid in run_ids if rid in self._records]

    def get_best_by_metric(self, metric: str = "ic") -> Optional[ExperimentRecord]:
        """Get the best experiment across all records by a metric."""
        records = list(self._records.values())
        completed = [r for r in records if r.status == "completed" and metric in r.metrics]
        if not completed:
            return None
        return max(completed, key=lambda r: r.metrics[metric])

    def search_by_tag(self, tag_key: str, tag_value: str) -> List[ExperimentRecord]:
        """Search experiments by tag."""
        tag_entry = f"{tag_key}:{tag_value}"
        run_ids = self._tag_index.get(tag_entry, [])
        return [self._records[rid] for rid in run_ids if rid in self._records]

    def list_recent(self, limit: int = 50) -> List[ExperimentRecord]:
        """List recent experiment records."""
        records = sorted(
            self._records.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )
        return records[:limit]

    # -- Analysis --

    def get_metric_history(self, metric: str = "ic") -> List[Dict[str, Any]]:
        """Get metric values over time for trend analysis."""
        history: List[Dict[str, Any]] = []
        for record in sorted(self._records.values(), key=lambda r: r.started_at):
            if metric in record.metrics:
                history.append({
                    "run_id": record.run_id,
                    "started_at": record.started_at.isoformat(),
                    "value": record.metrics[metric],
                })
        return history

    def compare_runs(self, run_ids: List[str]) -> List[Dict[str, Any]]:
        """Compare multiple experiment runs side-by-side."""
        return [
            record.to_summary()
            for rid in run_ids
            if (record := self._records.get(rid))
        ]
