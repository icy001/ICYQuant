from datetime import datetime

from services.execution.application.dead_letter_recovery import (
    DeadLetterRecoveryService,
)
from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.recovery import (
    RecoveryStatus,
)
from services.execution.infrastructure.memory_consumer_offset_store import (
    InMemoryConsumerOffsetStore,
)
from services.execution.infrastructure.memory_dead_letter_store import (
    InMemoryDeadLetterStore,
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


def build_dead_letter(
    event,
    consumer_id="position-service",
):
    return DeadLetterEvent(
        event=event,
        consumer_id=consumer_id,
        attempts=3,
        error="temporary failure",
        created_at=datetime.now(),
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

        raise RuntimeError(
            "still broken"
        )


def test_dead_letter_can_be_recovered():

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    dead_letter_store = (
        InMemoryDeadLetterStore()
    )

    event = build_event(
        event_id="event-100",
        request_id="exec-001",
        sequence=100,
    )

    dead_letter = build_dead_letter(
        event
    )

    dead_letter_store.save(
        dead_letter
    )

    consumer = RecordingConsumer(
        "position-service"
    )

    service = DeadLetterRecoveryService(
        dead_letter_store=dead_letter_store,
        offset_store=offset_store,
    )

    result = service.replay(
        dead_letter,
        consumer,
    )

    assert (
        result.status
        == RecoveryStatus.RECOVERED
    )

    assert (
        result.consumer_id
        == "position-service"
    )

    assert result.sequence == 100

    assert consumer.sequences == [
        100
    ]

    offset = offset_store.get(
        "position-service",
        "exec-001",
    )

    assert offset.sequence == 100


def test_failed_recovery_does_not_advance_offset():

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    dead_letter_store = (
        InMemoryDeadLetterStore()
    )

    event = build_event(
        event_id="event-100",
        request_id="exec-001",
        sequence=100,
    )

    dead_letter = build_dead_letter(
        event
    )

    consumer = FailingConsumer(
        consumer_id="position-service",
        fail_on_sequence=100,
    )

    service = DeadLetterRecoveryService(
        dead_letter_store=dead_letter_store,
        offset_store=offset_store,
    )

    result = service.replay(
        dead_letter,
        consumer,
    )

    assert (
        result.status
        == RecoveryStatus.FAILED
    )

    assert (
        result.error
        == "still broken"
    )

    assert (
        offset_store.get(
            "position-service",
            "exec-001",
        )
        is None
    )
