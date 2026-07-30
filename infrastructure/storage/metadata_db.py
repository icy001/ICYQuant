"""Metadata Database — persistent storage for feature store metadata.

Provides a database abstraction for feature registry, catalog,
lineage, and versioning metadata. Supports multiple backends
with a unified query interface.

Usage::

    from infrastructure.storage import MetadataDB

    db = MetadataDB()
    db.insert("feature_registry", {"feature_name": "ema20", "version": "v1"})
    results = db.query("feature_registry", {"feature_name": "ema20"})
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DatabaseBackend(str, Enum):
    """Supported database backends."""

    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass
class TableSchema:
    """Schema definition for a metadata table.

    Attributes:
        name: Table name.
        columns: Column name -> type mapping.
        primary_key: Primary key column(s).
        indexes: Index definitions.
        created_at: Schema creation timestamp.
    """

    name: str
    columns: Dict[str, str] = field(default_factory=dict)
    primary_key: List[str] = field(default_factory=lambda: ["id"])
    indexes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class QueryResult:
    """Result of a metadata query.

    Attributes:
        rows: Query result rows.
        total_count: Total matching rows (before limit/offset).
        query_time_ms: Query execution time in milliseconds.
    """

    rows: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0


class MetadataDB:
    """Persistent metadata storage for the Feature Store.

    Provides CRUD operations for feature registry, catalog,
    lineage, and versioning metadata. In production, backed by
    PostgreSQL; the MEMORY backend provides fast local development.
    """

    # ---- 分组：初始化 ----

    def __init__(self, backend: DatabaseBackend = DatabaseBackend.MEMORY) -> None:
        """Initialize the metadata database.

        Args:
            backend: Database backend to use.
        """
        self.backend = backend
        self._tables: Dict[str, TableSchema] = {}
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._id_counters: Dict[str, int] = {}

    # ---- 分组：表管理 ----

    def create_table(self, schema: TableSchema) -> TableSchema:
        """Create a new metadata table.

        Args:
            schema: Table schema definition.

        Returns:
            The created TableSchema.

        Raises:
            ValueError: If table already exists.
        """
        if schema.name in self._tables:
            raise ValueError(f"Table '{schema.name}' already exists.")
        self._tables[schema.name] = schema
        self._data[schema.name] = []
        self._id_counters[schema.name] = 0
        return schema

    def table_exists(self, name: str) -> bool:
        """Check if a table exists.

        Args:
            name: Table name.

        Returns:
            True if table exists.
        """
        return name in self._tables

    def list_tables(self) -> List[str]:
        """List all tables.

        Returns:
            Sorted table names.
        """
        return sorted(self._tables.keys())

    def get_schema(self, name: str) -> Optional[TableSchema]:
        """Get table schema.

        Args:
            name: Table name.

        Returns:
            TableSchema or None.
        """
        return self._tables.get(name)

    # ---- 分组：写入 ----

    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a row into a table.

        Args:
            table: Table name.
            row: Row data as dict.

        Returns:
            The inserted row (with auto-generated ID if applicable).

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        schema = self._tables[table]
        self._id_counters[table] += 1
        row["id"] = self._id_counters[table]
        row.setdefault("created_at", time.time())
        row.setdefault("updated_at", row["created_at"])

        self._data[table].append(dict(row))
        return dict(row)

    def insert_batch(self, table: str, rows: List[Dict[str, Any]]) -> int:
        """Insert multiple rows.

        Args:
            table: Table name.
            rows: List of row dicts.

        Returns:
            Number of rows inserted.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        for row in rows:
            self.insert(table, row)
        return len(rows)

    def update(
        self,
        table: str,
        query: Dict[str, Any],
        updates: Dict[str, Any],
    ) -> int:
        """Update rows matching a query.

        Args:
            table: Table name.
            query: Filter conditions.
            updates: Fields to update.

        Returns:
            Number of rows updated.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        count = 0
        updates["updated_at"] = time.time()
        for row in self._data[table]:
            if self._matches(row, query):
                row.update(updates)
                count += 1
        return count

    def upsert(
        self,
        table: str,
        query: Dict[str, Any],
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert or update a row.

        Args:
            table: Table name.
            query: Match conditions.
            row: Row data.

        Returns:
            The inserted or updated row.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        existing = self._find_one(table, query)
        if existing is not None:
            existing.update(row)
            existing["updated_at"] = time.time()
            return existing

        return self.insert(table, row)

    # ---- 分组：查询 ----

    def query(
        self,
        table: str,
        conditions: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> QueryResult:
        """Query rows from a table.

        Args:
            table: Table name.
            conditions: Filter conditions.
            order_by: Column to sort by.
            order_desc: Sort descending if True.
            limit: Maximum rows.
            offset: Skip N rows.

        Returns:
            QueryResult with matching rows.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        start_time = time.time()
        conditions = conditions or {}

        # Filter
        matching = [
            dict(row) for row in self._data[table]
            if self._matches(row, conditions)
        ]
        total_count = len(matching)

        # Sort
        if order_by:
            matching.sort(key=lambda r: r.get(order_by, ""), reverse=order_desc)

        # Paginate
        paginated = matching[offset : offset + limit]

        query_time = (time.time() - start_time) * 1000

        return QueryResult(
            rows=paginated,
            total_count=total_count,
            query_time_ms=query_time,
        )

    def find_one(
        self,
        table: str,
        conditions: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Find a single matching row.

        Args:
            table: Table name.
            conditions: Filter conditions.

        Returns:
            Row dict or None.

        Raises:
            KeyError: If table not found.
        """
        return self._find_one(table, conditions)

    def count(
        self,
        table: str,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count rows matching conditions.

        Args:
            table: Table name.
            conditions: Optional filter.

        Returns:
            Row count.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        conditions = conditions or {}
        return sum(1 for row in self._data[table] if self._matches(row, conditions))

    # ---- 分组：删除 ----

    def delete(
        self,
        table: str,
        conditions: Dict[str, Any],
    ) -> int:
        """Delete rows matching conditions.

        Args:
            table: Table name.
            conditions: Filter conditions.

        Returns:
            Number of rows deleted.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")

        before = len(self._data[table])
        self._data[table] = [
            row for row in self._data[table]
            if not self._matches(row, conditions)
        ]
        return before - len(self._data[table])

    def truncate(self, table: str) -> None:
        """Delete all rows from a table.

        Args:
            table: Table name.

        Raises:
            KeyError: If table not found.
        """
        if table not in self._data:
            raise KeyError(f"Table '{table}' not found.")
        self._data[table].clear()
        self._id_counters[table] = 0

    def drop_table(self, name: str) -> bool:
        """Drop a table.

        Args:
            name: Table name.

        Returns:
            True if dropped.
        """
        if name not in self._tables:
            return False
        del self._tables[name]
        del self._data[name]
        del self._id_counters[name]
        return True

    # ---- 分组：统计 ----

    def table_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a table.

        Args:
            name: Table name.

        Returns:
            Stats dict or None.
        """
        if name not in self._data:
            return None
        return {
            "table": name,
            "row_count": len(self._data[name]),
            "columns": list(self._tables[name].columns.keys()) if name in self._tables else [],
        }

    def db_stats(self) -> Dict[str, Any]:
        """Get aggregate database statistics.

        Returns:
            Stats dict.
        """
        return {
            "backend": self.backend.value,
            "table_count": len(self._tables),
            "tables": {
                name: {"row_count": len(rows)}
                for name, rows in self._data.items()
            },
            "total_rows": sum(len(rows) for rows in self._data.values()),
        }

    # ---- 分组：内部 ----

    def _find_one(self, table: str, conditions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single matching row without error handling."""
        for row in self._data.get(table, []):
            if self._matches(row, conditions):
                return dict(row)
        return None

    @staticmethod
    def _matches(row: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Check if a row matches all conditions."""
        for key, value in conditions.items():
            if key not in row or row[key] != value:
                return False
        return True
