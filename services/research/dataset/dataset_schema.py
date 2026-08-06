"""Dataset Schema — defines the structure and types of dataset columns.

Provides schema definition, validation, and evolution support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ColumnType(str, Enum):
    """Supported column data types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    CATEGORY = "category"
    JSON = "json"
    ARRAY = "array"


@dataclass
class ColumnSchema:
    """Schema definition for a single column."""

    name: str = ""
    column_type: ColumnType = ColumnType.STRING
    nullable: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "column_type": self.column_type.value,
            "nullable": self.nullable,
            "description": self.description,
            "metadata": self.metadata,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColumnSchema":
        return cls(
            name=data.get("name", ""),
            column_type=ColumnType(data.get("column_type", "string")),
            nullable=data.get("nullable", True),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            constraints=data.get("constraints", {}),
        )


@dataclass
class DatasetSchema:
    """Complete schema for a dataset.

    Defines:
    * Column names and types
    * Primary key / index columns
    * Partition columns
    * Schema version for evolution
    """

    dataset_id: str = ""
    columns: List[ColumnSchema] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    index_columns: List[str] = field(default_factory=list)
    partition_columns: List[str] = field(default_factory=list)
    timestamp_column: Optional[str] = None
    version: int = 1
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── column access ─────────────────────────────────────────────────────

    @property
    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def has_column(self, name: str) -> bool:
        return self.get_column(name) is not None

    def add_column(self, column: ColumnSchema) -> None:
        """Add a new column to the schema."""
        if self.has_column(column.name):
            raise ValueError(f"Column already exists: {column.name}")
        self.columns.append(column)

    def remove_column(self, name: str) -> bool:
        col = self.get_column(name)
        if col:
            self.columns.remove(col)
            return True
        return False

    # ── validation ────────────────────────────────────────────────────────

    def validate_columns(self, column_names: List[str]) -> List[str]:
        """Validate that given columns match schema. Returns list of errors."""
        errors: List[str] = []
        schema_names = set(self.column_names)

        missing = [c for c in self.column_names if c not in column_names]
        if missing:
            errors.append(f"Missing required columns: {missing}")

        extra = [c for c in column_names if c not in schema_names]
        if extra:
            errors.append(f"Unexpected columns: {extra}")

        return errors

    # ── serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "columns": [c.to_dict() for c in self.columns],
            "primary_keys": self.primary_keys,
            "index_columns": self.index_columns,
            "partition_columns": self.partition_columns,
            "timestamp_column": self.timestamp_column,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSchema":
        return cls(
            dataset_id=data.get("dataset_id", ""),
            columns=[ColumnSchema.from_dict(c) for c in data.get("columns", [])],
            primary_keys=data.get("primary_keys", []),
            index_columns=data.get("index_columns", []),
            partition_columns=data.get("partition_columns", []),
            timestamp_column=data.get("timestamp_column"),
            version=data.get("version", 1),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        return f"DatasetSchema(dataset={self.dataset_id[:8]}, columns={self.column_count}, v{self.version})"
