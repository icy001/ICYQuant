from __future__ import annotations

from services.execution.domain.event import ExecutionEvent
from services.execution.domain.journal import (
    ExecutionEventJournal,
)


class InMemoryExecutionEventJournal(
    ExecutionEventJournal
):

    def __init__(self) -> None:
        self._events: dict[
            str,
            ExecutionEvent,
        ] = {}

        self._request_index: dict[
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

        self._events[
            event.event_id
        ] = event

        self._request_index.setdefault(
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

    def list_by_execution_request(
        self,
        execution_request_id: str,
    ) -> list[ExecutionEvent]:

        event_ids = self._request_index.get(
            execution_request_id,
            [],
        )

        return [
            self._events[event_id]
            for event_id in event_ids
        ]
