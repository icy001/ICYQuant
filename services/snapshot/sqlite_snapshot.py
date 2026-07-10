"""
SQLite snapshot persistence.
"""

from __future__ import annotations


import json

import sqlite3


from uuid import UUID


from datetime import datetime


from .model import PortfolioSnapshot


class SQLiteSnapshotStore:
    def __init__(
        self,
        database_path: str,
    ) -> None:
        self.connection = sqlite3.connect(
            database_path
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self._init()

    def _init(
        self,
    ) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                created_at TEXT,
                state TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def save(
        self,
        snapshot: PortfolioSnapshot,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO snapshots
            VALUES (?, ?, ?, ?)
            """,
            (
                str(snapshot.snapshot_id),
                str(snapshot.event_id),
                snapshot.created_at.isoformat() if snapshot.created_at else None,
                json.dumps(
                    snapshot.state
                ),
            )
        )

        self.connection.commit()

    def latest(
        self,
    ) -> PortfolioSnapshot | None:
        cursor = self.connection.execute(
            """
            SELECT *
            FROM snapshots
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return PortfolioSnapshot(
            snapshot_id=UUID(
                row["snapshot_id"]
            ),
            event_id=UUID(
                row["event_id"]
            ),
            created_at=datetime.fromisoformat(
                row["created_at"]
            ) if row["created_at"] else None,
            state=json.loads(
                row["state"]
            ),
        )