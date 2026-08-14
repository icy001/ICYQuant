from datetime import datetime

import pytest

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.application.reliable_consumer import (
    ReliableExecutionConsumer,
)
from services.execution.domain.consumer_error import (
    ConsumerProcessingError,
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


class FailingConsumer(
    ExecutionEventConsumer
):

    def __init__(
        self,
        consumer_id,
        fail_on_sequence,
    ) -> None:

        self._consumer_id = consumer_id
        self._fail_on_sequence = (
            fail_on_sequence
        )

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    def handle(
        self,
        event: ExecutionEvent,
    ) -> None:

        if (
            event.sequence
            == self._fail_on_sequence
        ):
            raise RuntimeError(
                "position update failed"
            )


def test_failed_event_is_not_acked():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    consumer = FailingConsumer(
        consumer_id="position-service",
        fail_on_sequence=3,
    )

    for sequence in range(1, 5):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                request_id="exec-001",
                sequence=sequence,
            )
        )

    runner = ReliableExecutionConsumer(
        consumer=consumer,
        event_store=event_store,
        offset_store=offset_store,
    )

    with pytest.raises(
        ConsumerProcessingError
    ):
        runner.consume(
            "exec-001"
        )

    offset = offset_store.get(
        "position-service",
        "exec-001",
    )

    assert offset.sequence == 2
