"""
In-memory event store implementation.

Used for:

- Unit tests
- Backtesting
- Local research


The implementation follows
EventStore protocol.

No database dependency.
"""

from __future__ import annotations


from collections import defaultdict


from uuid import UUID


from typing import Iterable


from .event import LedgerEvent

from .exceptions import (
    DuplicateEventError,
)


class MemoryEventStore:
    """
    In-memory ledger event store.

    Events are stored append-only.

    Example:

        store.append(event)

        events = store.all_events()
    """



    def __init__(self) -> None:

        self._events: list[
            LedgerEvent
        ] = []


        self._event_index: dict[
            UUID,
            LedgerEvent
        ] = {}


        self._aggregate_index: dict[
            str,
            list[LedgerEvent]
        ] = defaultdict(list)




    def append(
        self,
        event: LedgerEvent,
    ) -> None:
        """
        Append one event.

        Ledger is append-only.
        Existing events cannot
        be modified.
        """


        if event.event_id in self._event_index:

            raise DuplicateEventError(

                f"Event already exists: "
                f"{event.event_id}"

            )


        self._events.append(
            event
        )


        self._event_index[
            event.event_id
        ] = event




        if event.aggregate_id:

            self._aggregate_index[
                event.aggregate_id
            ].append(
                event
            )




    def append_many(
        self,
        events: Iterable[LedgerEvent],
    ) -> None:
        """
        Append multiple events.

        Atomic behaviour:

        If one event fails,
        previous events remain unchanged.

        """

        events = list(events)


        existing_ids = set(
            self._event_index.keys()
        )


        for event in events:

            if event.event_id in existing_ids:

                raise DuplicateEventError(

                    f"Duplicate event: "
                    f"{event.event_id}"

                )


        for event in events:

            self.append(event)




    def get(
        self,
        event_id: UUID,
    ) -> LedgerEvent | None:
        """
        Retrieve event by UUID.
        """


        return self._event_index.get(
            event_id
        )




    def all_events(
        self,
    ) -> list[LedgerEvent]:
        """
        Return all ledger events.

        Events maintain insertion order.
        """


        return list(
            self._events
        )




    def stream(
        self,
        aggregate_id: str,
    ) -> list[LedgerEvent]:
        """
        Retrieve aggregate event stream.

        Example:

            Account-001

            |
            +-- Deposit
            +-- OrderFilled
            +-- Commission

        """


        return list(

            self._aggregate_index.get(
                aggregate_id,
                []
            )

        )




    def count(
        self,
    ) -> int:
        """
        Return total events.
        """


        return len(
            self._events
        )




    def clear(
        self,
    ) -> None:
        """
        Clear store.

        Mainly used in tests.
        """


        self._events.clear()

        self._event_index.clear()

        self._aggregate_index.clear()