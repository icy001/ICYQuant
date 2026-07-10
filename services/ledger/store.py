"""
Ledger event store abstraction.

Different environments use
different persistence engines:

Backtest:

    MemoryEventStore


Paper Trading:

    SQLiteEventStore


Production:

    PostgreSQLEventStore


All implementations follow
the same interface.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

from .event import LedgerEvent
from .exceptions import DuplicateEventError, EventStoreError


class EventStore(Protocol):
    """
    Event store interface.
    """

    def append(self, event: LedgerEvent) -> None:
        """
        Persist one event.
        """
        ...

    def append_many(self, events: Iterable[LedgerEvent]) -> None:
        """
        Persist multiple events.
        """
        ...

    def get(self, event_id: UUID) -> LedgerEvent | None:
        """
        Retrieve event by id.
        """
        ...

    def all_events(self) -> list[LedgerEvent]:
        """
        Return all events ordered
        by timestamp.
        """
        ...

    def stream(self, aggregate_id: str) -> list[LedgerEvent]:
        """
        Return events belonging
        to one aggregate.
        """
        ...


class InMemoryEventStore:
    """
    In-memory event store for backtesting.
    """

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._event_index: dict[UUID, LedgerEvent] = {}

    def append(self, event: LedgerEvent) -> None:
        if event.event_id in self._event_index:
            raise DuplicateEventError(f"Event with id {event.event_id} already exists")
        self._events.append(event)
        self._event_index[event.event_id] = event

    def append_many(self, events: Iterable[LedgerEvent]) -> None:
        for event in events:
            self.append(event)

    def get(self, event_id: UUID) -> LedgerEvent | None:
        return self._event_index.get(event_id)

    def all_events(self) -> list[LedgerEvent]:
        return sorted(self._events, key=lambda e: e.timestamp)

    def stream(self, aggregate_id: str) -> list[LedgerEvent]:
        return [e for e in self._events if e.aggregate_id == aggregate_id]


class SQLiteEventStore:
    """
    SQLite-backed event store for paper trading.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    aggregate_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_events_aggregate_id 
                ON ledger_events(aggregate_id)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_events_timestamp 
                ON ledger_events(timestamp)
            """)
            self._conn.commit()
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to initialize schema: {str(e)}")

    def append(self, event: LedgerEvent) -> None:
        try:
            cursor = self._conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO ledger_events 
                    (event_id, event_type, timestamp, aggregate_id, payload)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(event.event_id),
                        event.event_type.value,
                        event.timestamp.isoformat(),
                        event.aggregate_id,
                        json.dumps(event.payload),
                    ),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    raise DuplicateEventError(
                        f"Event with id {event.event_id} already exists"
                    )
                raise
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to append event: {str(e)}")

    def append_many(self, events: Iterable[LedgerEvent]) -> None:
        try:
            cursor = self._conn.cursor()
            try:
                for event in events:
                    cursor.execute(
                        """
                        INSERT INTO ledger_events 
                        (event_id, event_type, timestamp, aggregate_id, payload)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            str(event.event_id),
                            event.event_type.value,
                            event.timestamp.isoformat(),
                            event.aggregate_id,
                            json.dumps(event.payload),
                        ),
                    )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    raise DuplicateEventError("Duplicate event detected")
                raise
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to append events: {str(e)}")

    def get(self, event_id: UUID) -> LedgerEvent | None:
        try:
            self._conn.row_factory = sqlite3.Row
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT * FROM ledger_events 
                WHERE event_id = ?
                """,
                (str(event_id),),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to get event: {str(e)}")

    def all_events(self) -> list[LedgerEvent]:
        try:
            self._conn.row_factory = sqlite3.Row
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT * FROM ledger_events 
                ORDER BY timestamp ASC
                """
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to get all events: {str(e)}")

    def stream(self, aggregate_id: str) -> list[LedgerEvent]:
        try:
            self._conn.row_factory = sqlite3.Row
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT * FROM ledger_events 
                WHERE aggregate_id = ? 
                ORDER BY timestamp ASC
                """,
                (aggregate_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
        except sqlite3.Error as e:
            raise EventStoreError(f"Failed to get stream: {str(e)}")

    def _row_to_event(self, row: sqlite3.Row) -> LedgerEvent:
        from .event_type import LedgerEventType

        return LedgerEvent(
            event_id=UUID(row["event_id"]),
            event_type=LedgerEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            aggregate_id=row["aggregate_id"],
            payload=json.loads(row["payload"]),
        )