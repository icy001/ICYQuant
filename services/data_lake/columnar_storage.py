"""
Columnar Storage — column-oriented storage engine with column families
and schema management for the data lake.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ColumnDataType(str, Enum):
    STRING = "string"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    BINARY = "binary"
    JSON = "json"


@dataclass
class ColumnSchema:
    name: str
    data_type: ColumnDataType
    nullable: bool = True
    default_value: Any = None
    description: str = ""
    encoding: str = "plain"  # plain, dictionary, delta, rle
    statistics_enabled: bool = True
    bloom_filter_enabled: bool = False


@dataclass
class ColumnFamily:
    name: str
    columns: list[ColumnSchema]
    description: str = ""
    compression: str = "snappy"
    ttl_days: Optional[int] = None


class ColumnarStorage:
    """
    Column-oriented storage engine for the data lake.

    Manages column families, schemas, and provides efficient
    columnar reads with projection pushdown.
    """

    def __init__(self) -> None:
        self._column_families: dict[str, ColumnFamily] = {}
        self._schemas: dict[str, list[ColumnSchema]] = {}

    def register_family(self, family: ColumnFamily) -> None:
        """Register a column family."""
        self._column_families[family.name] = family
        self._schemas[family.name] = family.columns
        logger.info("Registered column family: %s (%d columns)", family.name, len(family.columns))

    def register_schema(self, table_name: str, columns: list[ColumnSchema]) -> None:
        """Register a table schema."""
        self._schemas[table_name] = columns
        logger.info("Registered schema: %s (%d columns)", table_name, len(columns))

    def get_schema(self, table_name: str) -> Optional[list[ColumnSchema]]:
        """Get the schema for a table."""
        return self._schemas.get(table_name)

    def get_column(self, table_name: str, column_name: str) -> Optional[ColumnSchema]:
        """Get a single column schema."""
        schema = self._schemas.get(table_name)
        if schema:
            for col in schema:
                if col.name == column_name:
                    return col
        return None

    def validate_columns(self, table_name: str, columns: list[str]) -> list[str]:
        """Validate column names exist in schema; returns missing columns."""
        schema = self._schemas.get(table_name)
        if not schema:
            return columns
        valid_names = {c.name for c in schema}
        return [c for c in columns if c not in valid_names]

    def get_projection(self, table_name: str, columns: Optional[list[str]] = None) -> list[str]:
        """Get the effective column projection (all columns if None)."""
        schema = self._schemas.get(table_name)
        if not schema:
            return columns or []
        if columns is None:
            return [c.name for c in schema]
        return [c for c in columns if c in {s.name for s in schema}]

    def list_families(self) -> list[dict[str, Any]]:
        return [
            {"name": f.name, "columns": len(f.columns), "compression": f.compression}
            for f in self._column_families.values()
        ]

    def list_schemas(self) -> list[str]:
        return list(self._schemas.keys())
