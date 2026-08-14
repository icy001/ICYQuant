from __future__ import annotations

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.event import (
    ExecutionEvent,
)


class ExecutionEventDispatcher:

    def __init__(self) -> None:

        self._consumers: dict[
            str,
            ExecutionEventConsumer,
        ] = {}

    def register(
        self,
        consumer: ExecutionEventConsumer,
    ) -> None:

        consumer_id = consumer.consumer_id

        if consumer_id in self._consumers:
            raise ValueError(
                f"consumer already registered: "
                f"{consumer_id}"
            )

        self._consumers[
            consumer_id
        ] = consumer

    def consumers(
        self,
    ) -> list[ExecutionEventConsumer]:

        return list(
            self._consumers.values()
        )

    def dispatch(
        self,
        event: ExecutionEvent,
    ) -> None:

        for consumer in self._consumers.values():
            consumer.handle(event)
