from __future__ import annotations

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.consumer_error import (
    ConsumerProcessingError,
)
from services.execution.domain.event import (
    ExecutionEvent,
)
from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)
from services.execution.ports.event_store import (
    ExecutionEventStore,
)


class ReliableExecutionConsumer:

    def __init__(
        self,
        consumer: ExecutionEventConsumer,
        event_store: ExecutionEventStore,
        offset_store: ConsumerOffsetStore,
    ) -> None:

        self._consumer = consumer
        self._event_store = event_store
        self._offset_store = offset_store

    def consume(
        self,
        stream_id: str,
    ) -> int:

        current = (
            self._offset_store.get(
                self._consumer.consumer_id,
                stream_id,
            )
        )

        after_sequence = (
            current.sequence
            if current is not None
            else 0
        )

        events = self._event_store.stream(
            stream_id,
            after_sequence=after_sequence,
        )

        last_sequence = after_sequence

        for event in events:

            try:
                self._consumer.handle(event)

            except Exception as exc:

                raise ConsumerProcessingError(
                    consumer_id=(
                        self._consumer.consumer_id
                    ),
                    sequence=event.sequence,
                    cause=exc,
                ) from exc

            self._offset_store.save(
                ConsumerOffset(
                    consumer_id=(
                        self._consumer.consumer_id
                    ),
                    stream_id=stream_id,
                    sequence=event.sequence,
                )
            )

            last_sequence = event.sequence

        return last_sequence
