from datetime import datetime

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.application.reliable_consumer import (
    ReliableExecutionConsumer,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.infrastructure.memory_consumer_offset_store import (
    InMemoryConsumerOffsetStore,
)
from services.execution.infrastructure.memory_event_store import (
    InMemoryExecutionEventStore,
)


def build_event(
    event_id="event-1",
    request_id="exec-001",
    sequence=1,
):
    return ExecutionEvent(
        event_id=event_id,
        execution_request_id=request_id,
        order_id="order-001",
        event_type=ExecutionEventType.FILLED,
        timestamp=datetime.now(),
        sequence=sequence,
    )


class RecordingConsumer(
    ExecutionEventConsumer
):

    def __init__(
        self,
        consumer_id,
    ) -> None:

        self._consumer_id = consumer_id
        self.sequences = []

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    def handle(
        self,
        event: ExecutionEvent,
    ) -> None:

        self.sequences.append(
            event.sequence
        )


def test_consumer_resumes_from_offset():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    consumer = RecordingConsumer(
        "position-service"
    )

    for sequence in range(1, 6):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                request_id="exec-001",
                sequence=sequence,
            )
        )

    offset_store.save(
        ConsumerOffset(
            consumer_id="position-service",
            stream_id="exec-001",
            sequence=3,
        )
    )

    runner = ReliableExecutionConsumer(
        consumer=consumer,
        event_store=event_store,
        offset_store=offset_store,
    )

    sequence = runner.consume(
        "exec-001"
    )

    assert sequence == 5

    assert consumer.sequences == [
        4,
        5,
    ]
