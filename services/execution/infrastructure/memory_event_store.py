from __future__ import annotations

from services.execution.domain.event import (
    ExecutionEvent,
)
from services.execution.domain.sequence import (
    validate_next_sequence,
)
from services.execution.ports.event_store import (
    ExecutionEventStore,
)


class InMemoryExecutionEventStore(
    ExecutionEventStore
):

    def __init__(self) -> None:

        self._events: dict[
            str,
            ExecutionEvent,
        ] = {}

        self._streams: dict[
            str,
            list[str],
        ] = {}

    def append(
        self,
        event: ExecutionEvent,
    ) -> None:

        if event.event_id in self._events:
            raise ValueError(
                f"event already exists: "
                f"{event.event_id}"
            )

        current = self.latest_sequence(
            event.execution_request_id
        )

        validate_next_sequence(
            current_sequence=current,
            next_sequence=event.sequence,
        )

        self._events[
            event.event_id
        ] = event

        self._streams.setdefault(
            event.execution_request_id,
            [],
        ).append(
            event.event_id
        )

    def get(
        self,
        event_id: str,
    ) -> ExecutionEvent | None:

        return self._events.get(
            event_id
        )

    def stream(
        self,
        execution_request_id: str,
        *,
        after_sequence: int = 0,
    ) -> list[ExecutionEvent]:

        event_ids = self._streams.get(
            execution_request_id,
            [],
        )

        events = [
            self._events[event_id]
            for event_id in event_ids
        ]

        return [
            event
            for event in events
            if event.sequence > after_sequence
        ]

    def latest_sequence(
        self,
        execution_request_id: str,
    ) -> int:

        event_ids = self._streams.get(
            execution_request_id,
            [],
        )

        if not event_ids:
            return 0

        return self._events[
            event_ids[-1]
        ].sequence
