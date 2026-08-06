"""Dataset Profile — automated data profiling and schema inference.

Provides comprehensive profiling of dataset columns including type detection,
value distribution analysis, null detection, and pattern recognition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from .dataset_schema import ColumnType


class ProfileStatus(str, Enum):
    """Profile generation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STALE = "stale"
    FAILED = "failed"


@dataclass
class ColumnProfile:
    """Statistical profile of a single column.

    Captures type, null counts, distinct values, and value patterns
    for data exploration and quality assessment.
    """

    column_name: str = ""
    column_type: ColumnType = ColumnType.STRING
    inferred_type: ColumnType = ColumnType.STRING
    count: int = 0
    null_count: int = 0
    null_ratio: float = 0.0
    distinct_count: int = 0
    distinct_ratio: float = 0.0
    unique_count: int = 0
    empty_count: int = 0
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    mean_length: Optional[float] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None
    top_values: List[Dict[str, Any]] = field(default_factory=list)
    sample_values: List[Any] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    is_nullable: bool = True
    is_unique: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_name": self.column_name,
            "column_type": self.column_type.value,
            "inferred_type": self.inferred_type.value,
            "count": self.count,
            "null_count": self.null_count,
            "null_ratio": self.null_ratio,
            "distinct_count": self.distinct_count,
            "distinct_ratio": self.distinct_ratio,
            "unique_count": self.unique_count,
            "empty_count": self.empty_count,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "mean_length": self.mean_length,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "std_value": self.std_value,
            "top_values": self.top_values,
            "sample_values": self.sample_values[:10],
            "patterns": self.patterns,
            "is_nullable": self.is_nullable,
            "is_unique": self.is_unique,
        }


@dataclass
class DatasetProfile:
    """Complete profile of a dataset including row/column level statistics.

    Generated automatically from data for rapid understanding
    without manual exploration.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    dataset_name: str = ""
    status: ProfileStatus = ProfileStatus.PENDING
    row_count: int = 0
    column_count: int = 0
    total_size_bytes: int = 0
    duplicate_rows: int = 0
    duplicate_ratio: float = 0.0
    complete_rows: int = 0
    complete_ratio: float = 0.0
    columns: List[ColumnProfile] = field(default_factory=list)
    correlations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    memory_usage_bytes: int = 0
    generation_time_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_column_profile(self, column_name: str) -> Optional[ColumnProfile]:
        """Get profile for a specific column."""
        for col in self.columns:
            if col.column_name == column_name:
                return col
        return None

    def highly_null_columns(self, threshold: float = 0.5) -> List[str]:
        """Return column names with null ratio above threshold."""
        return [c.column_name for c in self.columns if c.null_ratio > threshold]

    def constant_columns(self) -> List[str]:
        """Return column names with only one distinct value."""
        return [c.column_name for c in self.columns if c.distinct_count <= 1]

    def high_cardinality_columns(self, threshold: float = 0.9) -> List[str]:
        """Return columns with distinct ratio above threshold."""
        return [c.column_name for c in self.columns if c.distinct_ratio > threshold]

    def summary(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.dataset_name,
            "status": self.status.value,
            "rows": self.row_count,
            "columns": self.column_count,
            "duplicate_ratio": self.duplicate_ratio,
            "complete_ratio": self.complete_ratio,
            "memory_mb": round(self.memory_usage_bytes / (1024 * 1024), 2),
            "profile_time_ms": self.generation_time_ms,
            "highly_null_cols": len(self.highly_null_columns()),
            "constant_cols": len(self.constant_columns()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "status": self.status.value,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "total_size_bytes": self.total_size_bytes,
            "duplicate_rows": self.duplicate_rows,
            "duplicate_ratio": self.duplicate_ratio,
            "complete_rows": self.complete_rows,
            "complete_ratio": self.complete_ratio,
            "columns": [c.to_dict() for c in self.columns],
            "correlations": self.correlations,
            "memory_usage_bytes": self.memory_usage_bytes,
            "generation_time_ms": self.generation_time_ms,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"DatasetProfile(dataset={self.dataset_name}, "
            f"rows={self.row_count}, cols={self.column_count}, "
            f"status={self.status.value})"
        )
