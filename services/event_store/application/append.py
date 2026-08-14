"""Append event application service (Commit 34 Part 1.1 #7)."""

from __future__ import annotations

from services.event_store.domain.event import StoredEvent
from services.event_store.infrastructure.repository import EventStoreRepository


class AppendEvent:
    """Appends a new fact to the store.

    The application layer only depends on the repository - it never knows
    whether the store is PostgreSQL, Redis, Kafka or memory (#7).
    """

    def __init__(self, repository: EventStoreRepository) -> None:
        self.repository = repository

    def execute(self, event: StoredEvent) -> None:
        self.repository.append(event)
