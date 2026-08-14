from __future__ import annotations

from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.ports.dead_letter_store import (
    DeadLetterStore,
)


class InMemoryDeadLetterStore(
    DeadLetterStore
):

    def __init__(self) -> None:
        self._events: list[
            DeadLetterEvent
        ] = []

    def save(
        self,
        event: DeadLetterEvent,
    ) -> None:

        event.validate()

        self._events.append(event)

    def list(
        self,
        consumer_id: str | None = None,
    ) -> list[DeadLetterEvent]:

        if consumer_id is None:
            return list(self._events)

        return [
            event
            for event in self._events
            if event.consumer_id
            == consumer_id
        ]
