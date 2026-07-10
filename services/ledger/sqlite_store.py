"""
SQLite based event store.

Provides persistent storage
for ICYQuant ledger events.

Design:

- append only
- immutable events
- JSON payload
- ordered replay

Suitable for:

- local development
- paper trading
- small production deployments
"""

from __future__ import annotations


import json

import sqlite3


from pathlib import Path


from uuid import UUID


from datetime import datetime


from typing import Iterable


from .event import LedgerEvent


from .event_type import LedgerEventType


from .exceptions import (
    DuplicateEventError,
    EventStoreError,
)



class SQLiteEventStore:
    """
    SQLite implementation
    of Ledger Event Store.
    """


    def __init__(
        self,
        database_path: str | Path,
    ) -> None:


        self.database_path = str(
            database_path
        )


        self._connection = sqlite3.connect(
            self.database_path
        )


        self._connection.row_factory = (
            sqlite3.Row
        )


        self._initialize()




    def _initialize(
        self,
    ) -> None:
        """
        Create database schema.
        """


        sql = """

        CREATE TABLE IF NOT EXISTS ledger_events (

            event_id TEXT PRIMARY KEY,

            event_type TEXT NOT NULL,

            aggregate_id TEXT,

            timestamp TEXT NOT NULL,

            payload TEXT NOT NULL

        );

        """


        self._connection.execute(
            sql
        )


        self._connection.commit()




    def append(
        self,
        event: LedgerEvent,
    ) -> None:
        """
        Persist single event.
        """


        try:


            self._connection.execute(

                """

                INSERT INTO ledger_events

                (

                    event_id,

                    event_type,

                    aggregate_id,

                    timestamp,

                    payload

                )

                VALUES

                (

                    ?,

                    ?,

                    ?,

                    ?,

                    ?

                )

                """,

                (

                    str(event.event_id),

                    event.event_type.value,

                    event.aggregate_id,

                    event.timestamp.isoformat(),

                    json.dumps(
                        dict(event.payload)
                    ),

                ),

            )


            self._connection.commit()




        except sqlite3.IntegrityError as exc:


            raise DuplicateEventError(

                f"Event exists: "
                f"{event.event_id}"

            ) from exc




        except Exception as exc:


            raise EventStoreError(
                str(exc)
            ) from exc




    def append_many(
        self,
        events: Iterable[LedgerEvent],
    ) -> None:
        """
        Batch insert events.
        """


        try:


            with self._connection:


                for event in events:


                    self.append(
                        event
                    )




        except Exception:


            raise




    def get(
        self,
        event_id: UUID,
    ) -> LedgerEvent | None:
        """
        Load event by id.
        """


        cursor = self._connection.execute(

            """

            SELECT *

            FROM ledger_events

            WHERE event_id = ?

            """,

            (
                str(event_id),
            ),

        )


        row = cursor.fetchone()


        if row is None:


            return None




        return self._row_to_event(
            row
        )




    def all_events(
        self,
    ) -> list[LedgerEvent]:
        """
        Load all events ordered by time.
        """


        cursor = self._connection.execute(

            """

            SELECT *

            FROM ledger_events

            ORDER BY timestamp ASC

            """

        )


        return [

            self._row_to_event(row)

            for row in cursor.fetchall()

        ]




    def stream(
        self,
        aggregate_id: str,
    ) -> list[LedgerEvent]:
        """
        Load aggregate event stream.
        """


        cursor = self._connection.execute(

            """

            SELECT *

            FROM ledger_events

            WHERE aggregate_id = ?

            ORDER BY timestamp ASC

            """,

            (
                aggregate_id,
            ),

        )


        return [

            self._row_to_event(row)

            for row in cursor.fetchall()

        ]




    def close(
        self,
    ) -> None:
        """
        Close database connection.
        """


        self._connection.close()




    @staticmethod
    def _row_to_event(
        row: sqlite3.Row,
    ) -> LedgerEvent:
        """
        Convert database row
        back to domain event.
        """


        return LedgerEvent(

            event_id=UUID(
                row["event_id"]
            ),


            event_type=
            LedgerEventType(
                row["event_type"]
            ),


            aggregate_id=
            row["aggregate_id"],


            timestamp=
            datetime.fromisoformat(
                row["timestamp"]
            ),


            payload=
            json.loads(
                row["payload"]
            ),

        )