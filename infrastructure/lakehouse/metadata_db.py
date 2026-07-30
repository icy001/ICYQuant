"""ICYQuant Metadata Database.

Lightweight metadata database for the lakehouse.
Stores table schemas, partition info, file listings, and transaction state.

In production, this would use PostgreSQL or a similar relational database.
Here we use a JSON-file-backed in-memory store for portability.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TransactionState(str, Enum):
    """Transaction states."""

    ACTIVE = "active"
    COMMITTED = "committed"
    ABORTED = "aborted"


@dataclass
class TableRecord:
    """A table/dataset record in the metadata database."""

    table_id: str
    name: str
    schema_json: str = "{}"
    partition_spec: str = "{}"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    properties: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "schema_json": self.schema_json,
            "partition_spec": self.partition_spec,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "properties": self.properties,
        }


@dataclass
class FileRecord:
    """A file record in the metadata database."""

    file_id: str
    table_name: str
    partition: str
    file_path: str
    format: str = "parquet"
    row_count: int = 0
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "table_name": self.table_name,
            "partition": self.partition,
            "file_path": self.file_path,
            "format": self.format,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Transaction:
    """A database transaction."""

    transaction_id: str
    state: TransactionState = TransactionState.ACTIVE
    operations: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    committed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "state": self.state.value,
            "operations": self.operations,
            "started_at": self.started_at.isoformat(),
            "committed_at": self.committed_at.isoformat() if self.committed_at else None,
        }


class MetadataDB:
    """Lightweight Metadata Database.

    Manages table metadata, file listings, and ACID transactions
    for the lakehouse. Uses a JSON-file-backed store.

    Usage::

        db = MetadataDB(db_path="data/lakehouse/metadata.json")
        db.create_table("market_tick", schema_json, partition_spec)
        db.add_file("market_tick", file_record)
        files = db.get_files("market_tick", partition="2026-07-29")
    """

    def __init__(self, db_path: str = "data/lakehouse/metadata.json") -> None:
        self.db_path = db_path
        self._tables: Dict[str, TableRecord] = {}
        self._files: Dict[str, FileRecord] = {}
        self._transactions: Dict[str, Transaction] = {}

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Table Operations
    # ------------------------------------------------------------------

    def create_table(
        self,
        name: str,
        schema_json: str = "{}",
        partition_spec: str = "{}",
        **properties: str,
    ) -> TableRecord:
        """Create a table record.

        Args:
            name: Table name.
            schema_json: JSON schema string.
            partition_spec: JSON partition spec.
            **properties: Additional properties.

        Returns:
            TableRecord.
        """
        if name in self._tables:
            raise ValueError(f"Table '{name}' already exists")

        record = TableRecord(
            table_id=str(uuid.uuid4()),
            name=name,
            schema_json=schema_json,
            partition_spec=partition_spec,
            properties=properties,
        )
        self._tables[name] = record
        self._save()
        return record

    def get_table(self, name: str) -> Optional[TableRecord]:
        """Get a table record by name."""
        return self._tables.get(name)

    def list_tables(self) -> List[TableRecord]:
        """List all tables."""
        return list(self._tables.values())

    def update_table(
        self, name: str, **kwargs: Any
    ) -> Optional[TableRecord]:
        """Update a table record."""
        record = self._tables.get(name)
        if not record:
            return None

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = datetime.utcnow()
        self._save()
        return record

    def drop_table(self, name: str) -> bool:
        """Drop a table and all its files."""
        if name not in self._tables:
            return False

        del self._tables[name]
        # Remove associated files
        self._files = {
            fid: f for fid, f in self._files.items()
            if f.table_name != name
        }
        self._save()
        return True

    # ------------------------------------------------------------------
    # File Operations
    # ------------------------------------------------------------------

    def add_file(self, file_record: FileRecord) -> FileRecord:
        """Add a file record.

        Args:
            file_record: FileRecord to add.

        Returns:
            The added FileRecord.
        """
        self._files[file_record.file_id] = file_record
        self._save()
        return file_record

    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Get a file record by ID."""
        return self._files.get(file_id)

    def get_files(
        self,
        table_name: str,
        partition: Optional[str] = None,
    ) -> List[FileRecord]:
        """Get files for a table, optionally filtered by partition.

        Args:
            table_name: Table name.
            partition: Partition filter.

        Returns:
            List of FileRecord.
        """
        results = [
            f for f in self._files.values()
            if f.table_name == table_name
        ]
        if partition:
            results = [f for f in results if f.partition == partition]
        return results

    def get_file_count(self, table_name: str) -> int:
        """Get file count for a table."""
        return len(self.get_files(table_name))

    def get_total_size(self, table_name: str) -> int:
        """Get total size in bytes for a table."""
        return sum(f.size_bytes for f in self.get_files(table_name))

    def delete_file(self, file_id: str) -> bool:
        """Delete a file record."""
        if file_id in self._files:
            del self._files[file_id]
            self._save()
            return True
        return False

    # ------------------------------------------------------------------
    # Transaction Support
    # ------------------------------------------------------------------

    def begin_transaction(self) -> Transaction:
        """Start a new transaction.

        Returns:
            Transaction.
        """
        txn = Transaction(transaction_id=str(uuid.uuid4()))
        self._transactions[txn.transaction_id] = txn
        return txn

    def commit_transaction(self, transaction_id: str) -> bool:
        """Commit a transaction.

        Args:
            transaction_id: Transaction ID.

        Returns:
            True if committed.
        """
        txn = self._transactions.get(transaction_id)
        if not txn or txn.state != TransactionState.ACTIVE:
            return False

        txn.state = TransactionState.COMMITTED
        txn.committed_at = datetime.utcnow()
        self._save()
        return True

    def abort_transaction(self, transaction_id: str) -> bool:
        """Abort/rollback a transaction.

        Args:
            transaction_id: Transaction ID.

        Returns:
            True if aborted.
        """
        txn = self._transactions.get(transaction_id)
        if not txn or txn.state != TransactionState.ACTIVE:
            return False

        # Rollback operations
        for op in reversed(txn.operations):
            self._rollback_operation(op)

        txn.state = TransactionState.ABORTED
        return True

    def _rollback_operation(self, op: Dict[str, Any]) -> None:
        """Rollback a single operation."""
        op_type = op.get("type")
        if op_type == "add_file":
            file_id = op.get("file_id")
            if file_id:
                self._files.pop(file_id, None)
        elif op_type == "create_table":
            name = op.get("name")
            if name:
                self._tables.pop(name, None)

    def add_operation(self, transaction_id: str, op: Dict[str, Any]) -> bool:
        """Add an operation to a transaction.

        Args:
            transaction_id: Transaction ID.
            op: Operation dict.

        Returns:
            True if added.
        """
        txn = self._transactions.get(transaction_id)
        if not txn or txn.state != TransactionState.ACTIVE:
            return False

        txn.operations.append(op)
        return True

    # ------------------------------------------------------------------
    # Query Helpers
    # ------------------------------------------------------------------

    def get_partitions(self, table_name: str) -> List[str]:
        """Get distinct partitions for a table."""
        partitions = set()
        for f in self._files.values():
            if f.table_name == table_name:
                partitions.add(f.partition)
        return sorted(partitions)

    def get_latest_files(self, table_name: str, limit: int = 10) -> List[FileRecord]:
        """Get the most recently added files for a table."""
        files = self.get_files(table_name)
        files.sort(key=lambda f: f.created_at, reverse=True)
        return files[:limit]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "total_tables": len(self._tables),
            "total_files": len(self._files),
            "total_transactions": len(self._transactions),
            "active_transactions": sum(
                1 for t in self._transactions.values()
                if t.state == TransactionState.ACTIVE
            ),
            "tables": [
                {
                    "name": t.name,
                    "files": self.get_file_count(t.name),
                    "size_bytes": self.get_total_size(t.name),
                    "partitions": len(self.get_partitions(t.name)),
                }
                for t in self._tables.values()
            ],
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load database state from disk."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    state = json.load(f)

                for t_data in state.get("tables", []):
                    record = TableRecord(
                        table_id=t_data["table_id"],
                        name=t_data["name"],
                        schema_json=t_data.get("schema_json", "{}"),
                        partition_spec=t_data.get("partition_spec", "{}"),
                        created_at=datetime.fromisoformat(t_data["created_at"]),
                        updated_at=datetime.fromisoformat(t_data["updated_at"]),
                        properties=t_data.get("properties", {}),
                    )
                    self._tables[record.name] = record

                for f_data in state.get("files", []):
                    record = FileRecord(
                        file_id=f_data["file_id"],
                        table_name=f_data["table_name"],
                        partition=f_data["partition"],
                        file_path=f_data["file_path"],
                        format=f_data.get("format", "parquet"),
                        row_count=f_data.get("row_count", 0),
                        size_bytes=f_data.get("size_bytes", 0),
                        created_at=datetime.fromisoformat(f_data["created_at"]),
                    )
                    self._files[record.file_id] = record

            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        """Persist database state to disk."""
        state = {
            "tables": [t.to_dict() for t in self._tables.values()],
            "files": [f.to_dict() for f in self._files.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(self.db_path, "w") as f:
            json.dump(state, f, indent=2, default=str)
