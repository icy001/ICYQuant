"""Event store repository boundary (Commit 34 Part 1.1 #4 / Part 1.2 #5).

Part 1.2 extends the append-only contract with optimistic concurrency
control: ``current_version``, ``begin()`` and atomic ``append_stream``.
There is intentionally still no ``delete()`` or ``update()``: the event
store is append-only (#4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Optional, Tuple

from services.event_store.domain.event import StoredEvent
from services.event_store.infrastructure.transaction import EventStoreTransaction


class EventStoreRepository(ABC):
    """Append-only store contract with stream concurrency control."""

    @abstractmethod
    def append(self, event: StoredEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, event_id: str) -> Optional[StoredEvent]:
        raise NotImplementedError

    @abstractmethod
    def load_stream(self, aggregate_id: str) -> Iterable[StoredEvent]:
        raise NotImplementedError

    @abstractmethod
    def current_version(self, aggregate_id: str) -> int:
        """Return the latest stream version (0 for an unknown stream)."""
        raise NotImplementedError

    @abstractmethod
    def begin(self) -> EventStoreTransaction:
        """Open a transaction for an atomic stream append (#6)."""
        raise NotImplementedError

    @abstractmethod
    def append_stream(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        """Atomically append a batch, guarded by ``expected_version`` (#5)."""
        raise NotImplementedError
