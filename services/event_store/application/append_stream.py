"""Append event stream application service (Commit 34 Part 1.2 #6).

The application layer opens a transaction on the repository, appends the
whole batch under an expected version and commits - or rolls everything
back on failure.  It never knows whether the store is PostgreSQL, Redis,
Kafka or memory (#7).
"""

from __future__ import annotations

from typing import Tuple

from services.event_store.domain.event import StoredEvent
from services.event_store.infrastructure.repository import EventStoreRepository


class AppendEventStream:

    def __init__(self, repository: EventStoreRepository) -> None:
        self.repository = repository

    def execute(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        transaction = self.repository.begin()

        try:
            transaction.append_stream(
                aggregate_id,
                expected_version,
                events,
            )

            transaction.commit()

        except Exception:
            transaction.rollback()
            raise
