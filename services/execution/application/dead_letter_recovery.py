from __future__ import annotations

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.domain.recovery import (
    RecoveryResult,
    RecoveryStatus,
)
from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)
from services.execution.ports.dead_letter_store import (
    DeadLetterStore,
)


class DeadLetterRecoveryService:

    def __init__(
        self,
        dead_letter_store: DeadLetterStore,
        offset_store: ConsumerOffsetStore,
    ) -> None:

        self._dead_letter_store = (
            dead_letter_store
        )

        self._offset_store = offset_store

    def replay(
        self,
        dead_letter: DeadLetterEvent,
        consumer: ExecutionEventConsumer,
    ) -> RecoveryResult:

        event = dead_letter.event

        try:

            consumer.handle(event)

        except Exception as exc:

            return RecoveryResult(
                status=RecoveryStatus.FAILED,
                consumer_id=(
                    consumer.consumer_id
                ),
                stream_id=(
                    event.execution_request_id
                ),
                sequence=event.sequence,
                error=str(exc),
            )

        self._offset_store.save(
            ConsumerOffset(
                consumer_id=(
                    consumer.consumer_id
                ),
                stream_id=(
                    event.execution_request_id
                ),
                sequence=event.sequence,
            )
        )

        return RecoveryResult(
            status=RecoveryStatus.RECOVERED,
            consumer_id=(
                consumer.consumer_id
            ),
            stream_id=(
                event.execution_request_id
            ),
            sequence=event.sequence,
        )
