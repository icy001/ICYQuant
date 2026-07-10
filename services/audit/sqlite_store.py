"""
SQLite audit persistence.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from uuid import UUID

from .model import AuditRecord


class SQLiteAuditStore:
    def __init__(
        self,
        database_path: str,
    ):
        self.connection = sqlite3.connect(
            database_path
        )
        self.connection.row_factory = (
            sqlite3.Row
        )
        self._init()

    def _init(
        self,
    ):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_records (
                audit_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                source TEXT NOT NULL,
                reference_id TEXT,
                before_state TEXT,
                after_state TEXT,
                reason TEXT,
                created_at TEXT
            )
            """
        )
        self.connection.commit()

    def append(
        self,
        record: AuditRecord,
    ):
        self.connection.execute(
            """
            INSERT INTO audit_records
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.audit_id),
                record.action,
                record.source,
                (
                    str(record.reference_id)
                    if record.reference_id
                    else None
                ),
                json.dumps(
                    record.before
                ),
                json.dumps(
                    record.after
                ),
                record.reason,
                (
                    record.created_at.isoformat()
                    if record.created_at
                    else None
                ),
            )
        )
        self.connection.commit()

    def list_all(
        self,
    ):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM audit_records
            ORDER BY created_at
            """
        )
        return [
            AuditRecord(
                audit_id=UUID(
                    row["audit_id"]
                ),
                action=row["action"],
                source=row["source"],
                reference_id=(
                    UUID(row["reference_id"])
                    if row["reference_id"]
                    else None
                ),
                before=json.loads(
                    row["before_state"]
                ),
                after=json.loads(
                    row["after_state"]
                ),
                reason=row["reason"],
                created_at=(
                    datetime.fromisoformat(
                        row["created_at"]
                    )
                    if row["created_at"]
                    else None
                )
            )
            for row in cursor.fetchall()
        ]