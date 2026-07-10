from datetime import datetime
from typing import Iterable, List, Optional, Union
from uuid import UUID

from ..event import LedgerEvent
from ..event_type import LedgerEventType
from ..store import EventStore


class EventRepository:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store

    def save(self, event: LedgerEvent) -> None:
        self._event_store.append(event)

    def save_all(self, events: List[LedgerEvent]) -> None:
        self._event_store.append_many(events)

    def get_by_id(self, event_id: UUID) -> Optional[LedgerEvent]:
        return self._event_store.get(event_id)

    def get_by_stream(self, stream_id: str = "default") -> List[LedgerEvent]:
        return self._event_store.stream(stream_id)

    def get_by_type(self, event_type: LedgerEventType) -> List[LedgerEvent]:
        all_events = self._event_store.all_events()
        return [e for e in all_events if e.event_type == event_type]

    def get_by_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> List[LedgerEvent]:
        all_events = self._event_store.all_events()
        return [
            e
            for e in all_events
            if start_time <= e.timestamp <= end_time
        ]

    def get_all(self) -> List[LedgerEvent]:
        return self._event_store.all_events()

    def replay(self) -> List[LedgerEvent]:
        return self._event_store.all_events()


class LedgerRepository:
    """
    High level Ledger access layer.

    Example:

        repository.append(event)

        repository.events()

    """

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def append(self, event: LedgerEvent) -> None:
        """
        Append one ledger event.
        """
        self._store.append(event)

    def append_many(self, events: Iterable[LedgerEvent]) -> None:
        """
        Append multiple events.
        """
        self._store.append_many(events)

    def get(self, event_id: UUID) -> Optional[LedgerEvent]:
        """
        Retrieve event.
        """
        return self._store.get(event_id)

    def events(self) -> list[LedgerEvent]:
        """
        Return complete ledger history.
        """
        return self._store.all_events()

    def stream(self, aggregate_id: str) -> list[LedgerEvent]:
        """
        Return aggregate history.

        Example:

            PORTFOLIO-001

                |
                + Deposit
                + Buy NVDA
                + Commission

        """
        return self._store.stream(aggregate_id)

    def replay_source(self) -> Iterable[LedgerEvent]:
        """
        Provide event stream
        for projection replay.
        """
        yield from self.events()