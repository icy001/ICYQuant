"""
ICYQuant Training Dataset - Structured training data for ML models.

A Training Dataset combines features, labels, time, universe, and filters
into a reproducible artifact that fully documents what data was used for
training a specific model.

    Features
       +
    Labels
       +
    Time
       +
    Universe
       +
    Filters
       ↓
    Training Dataset
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
class DatasetMetadata:
    """Complete metadata for a training dataset."""

    dataset_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Features
    feature_ids: List[str] = field(default_factory=list)
    feature_versions: Dict[str, str] = field(default_factory=dict)  # feature_id -> version_id
    feature_count: int = 0

    # Labels
    label_type: str = "regression"  # classification, regression, ranking
    label_horizon: str = "5d"       # 1d, 5d, 10d, 20d
    label_column: str = "forward_return"

    # Data scope
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entity_ids: List[str] = field(default_factory=list)
    entity_count: int = 0

    # Data shape
    row_count: int = 0
    feature_dim: int = 0
    null_ratio: float = 0.0

    # Splits
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    val_start: Optional[datetime] = None
    val_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None

    # Filters applied
    filters: List[str] = field(default_factory=list)
    universe_filters: List[str] = field(default_factory=list)

    # Reproducibility
    snapshot_id: Optional[str] = None
    code_version: str = ""
    environment_hash: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute a dataset identity hash for reproducibility verification."""
        content = {
            "feature_ids": sorted(self.feature_ids),
            "versions": sorted(self.feature_versions.items()),
            "label_type": self.label_type,
            "label_horizon": self.label_horizon,
            "start": self.start_date.isoformat() if self.start_date else "",
            "end": self.end_date.isoformat() if self.end_date else "",
            "entity_count": self.entity_count,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]

    def get_split_dates(self) -> Dict[str, Dict[str, Optional[datetime]]]:
        """Get train/val/test split boundaries."""
        return {
            "train": {"start": self.train_start, "end": self.train_end},
            "validation": {"start": self.val_start, "end": self.val_end},
            "test": {"start": self.test_start, "end": self.test_end},
        }


class TrainingDataset:
    """A fully-documented training dataset for ML models.

    Encapsulates:
    - Features (with versions)
    - Labels (with type and horizon)
    - Time range (with train/val/test splits)
    - Universe and filters
    - Reproducibility metadata

    Enables answering: "What data was used to train this model?"
    """

    def __init__(self, metadata: DatasetMetadata, data: Any = None, labels: Any = None) -> None:
        self.metadata = metadata
        self._data = data       # Feature matrix (pandas DataFrame or similar)
        self._labels = labels   # Label vector/series

    @property
    def dataset_id(self) -> str:
        return self.metadata.dataset_id

    @property
    def feature_ids(self) -> List[str]:
        return self.metadata.feature_ids

    @property
    def shape(self) -> tuple:
        return (self.metadata.row_count, self.metadata.feature_dim)

    def get_features(self) -> Any:
        """Get the feature matrix."""
        return self._data

    def get_labels(self) -> Any:
        """Get the label vector."""
        return self._labels

    def get_train_data(self) -> tuple:
        """Get (X_train, y_train)."""
        # Placeholder: actual time-based splitting in production
        return self._data, self._labels

    def get_val_data(self) -> tuple:
        """Get (X_val, y_val)."""
        return None, None

    def get_test_data(self) -> tuple:
        """Get (X_test, y_test)."""
        return None, None

    def to_summary(self) -> Dict[str, Any]:
        """Generate a human-readable summary."""
        return {
            "dataset_id": self.metadata.dataset_id,
            "features": self.metadata.feature_count,
            "entities": self.metadata.entity_count,
            "rows": self.metadata.row_count,
            "feature_dim": self.metadata.feature_dim,
            "label_type": self.metadata.label_type,
            "label_horizon": self.metadata.label_horizon,
            "date_range": f"{self.metadata.start_date} to {self.metadata.end_date}" if self.metadata.start_date else "N/A",
            "null_ratio": f"{self.metadata.null_ratio:.2%}",
            "hash": self.metadata.compute_hash(),
        }
