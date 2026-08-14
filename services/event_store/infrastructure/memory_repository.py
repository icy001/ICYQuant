"""In-memory event store with transactional appends (Commit 34 Part 1.2).

Internal layout follows Part 1.2 #10:

.. code-block:: text

    _streams
    |-- ORDER-001  [v1, v2, v3]
    |-- ORDER-002  [v1, v2]
    `-- ORDER-003  []

    _by_id                    # event_id -> event, for idempotency checks
    |-- EVT-ORD-000001 -> OrderCreated(v1)
    |-- ...

A transaction takes a snapshot of both structures on ``begin()``; ``commit()``
discards the snapshot and ``rollback()`` restores it (#11) - this lets tests
simulate a database transaction without PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Dict, List, Optional, Tuple

from services.event_store.domain.errors import (
    ConcurrencyConflictError,
    EventAlreadyExistsError,
    InvalidEventVersionError,
)
from services.event_store.domain.event import StoredEvent
from services.event_store.domain.stream import (
    ensure_event_identity,
    validate_event_sequence,
)
from services.event_store.infrastructure.repository import EventStoreRepository
from services.event_store.infrastructure.transaction import EventStoreTransaction

Snapshot = Tuple[Dict[str, List[StoredEvent]], Dict[str, StoredEvent]]


class InMemoryEventStoreRepository(EventStoreRepository):
    """Append-only in-memory store with OCC and atomic stream appends (#10)."""

    def __init__(self) -> None:
        self._streams: Dict[str, List[StoredEvent]] = {}
        self._by_id: Dict[str, StoredEvent] = {}

    # ------------------------------------------------------------------
    # Part 1.1 contract (kept byte-for-byte strict for backward compat)
    # ------------------------------------------------------------------

    def append(self, event: StoredEvent) -> None:
        if event.event_id in self._by_id:
            raise EventAlreadyExistsError(event.event_id)
        stream = self._streams.setdefault(event.aggregate_id, [])
        if stream:
            expected_version = stream[-1].aggregate_version + 1
            if event.aggregate_version != expected_version:
                raise InvalidEventVersionError(
                    f"expected={expected_version}, "
                    f"actual={event.aggregate_version}"
                )
        stream.append(event)
        self._by_id[event.event_id] = event

    def get(self, event_id: str) -> Optional[StoredEvent]:
        return self._by_id.get(event_id)

    def load_stream(self, aggregate_id: str) -> Iterable[StoredEvent]:
        return list(self._streams.get(aggregate_id, []))

    # ------------------------------------------------------------------
    # Part 1.2 concurrency control
    # ------------------------------------------------------------------

    def current_version(self, aggregate_id: str) -> int:
        stream = self._streams.get(aggregate_id, [])
        return stream[-1].aggregate_version if stream else 0

    def begin(self) -> EventStoreTransaction:
        return InMemoryEventStoreTransaction(self)

    def append_stream(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        transaction = self.begin()
        try:
            transaction.append_stream(aggregate_id, expected_version, events)
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise

    # ------------------------------------------------------------------
    # internal machinery used by the transaction
    # ------------------------------------------------------------------

    def _snapshot(self) -> Snapshot:
        return (
            {aggregate_id: list(stream) for aggregate_id, stream in self._streams.items()},
            dict(self._by_id),
        )

    def _restore(self, snapshot: Snapshot) -> None:
        self._streams, self._by_id = snapshot

    def _all_exist_idempotently(self, events: Tuple[StoredEvent, ...]) -> bool:
        if not events:
            return False
        for event in events:
            existing = self._by_id.get(event.event_id)
            if existing is None or existing.payload != event.payload:
                return False
        return True

    def _validate_and_apply(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        # 1. identity protection: the same event_id must carry the same fact (#9)
        for event in events:
            existing = self._by_id.get(event.event_id)
            if existing is not None:
                ensure_event_identity(existing, event)

        # 2. full-batch idempotent retry -> success without writing anything
        if self._all_exist_idempotently(events):
            return

        # 3. optimistic concurrency control (#4)
        current = self.current_version(aggregate_id)
        if current != expected_version:
            raise ConcurrencyConflictError(
                aggregate_id,
                expected_version,
                current,
            )

        # 4. stream sequence validation (#8)
        validate_event_sequence(expected_version, events)

        # 5. apply
        for event in events:
            self._streams.setdefault(aggregate_id, []).append(event)
            self._by_id[event.event_id] = event


class InMemoryEventStoreTransaction(EventStoreTransaction):
    """Snapshot-based transaction over :class:`InMemoryEventStoreRepository` (#11)."""

    def __init__(self, repository: InMemoryEventStoreRepository) -> None:
        self._repository = repository
        self._snapshot = repository._snapshot()
        self._finished = False

    def append_stream(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        self._repository._validate_and_apply(
            aggregate_id,
            expected_version,
            events,
        )

    def commit(self) -> None:
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            return
        self._repository._restore(self._snapshot)
        self._finished = True
