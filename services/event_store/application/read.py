"""Read stream application service (Commit 34 Part 1.1 #8)."""

from __future__ import annotations

from collections.abc import Iterable

from services.event_store.domain.event import StoredEvent
from services.event_store.infrastructure.repository import EventStoreRepository


class ReadEventStream:
    """Reads the full event stream of an aggregate in version order.

    ``read_stream("ORDER-001")`` returns v1, v2, v3, ... - the basis for replay,
    rebuild, audit and projection (#10).
    """

    def __init__(self, repository: EventStoreRepository) -> None:
        self.repository = repository

    def execute(self, aggregate_id: str) -> Iterable[StoredEvent]:
        return self.repository.load_stream(aggregate_id)
