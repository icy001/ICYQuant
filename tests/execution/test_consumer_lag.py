from datetime import datetime

from services.execution.application.consumer_lag import (
    ConsumerLagService,
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


def test_consumer_lag():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    for sequence in range(1, 11):

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
            sequence=7,
        )
    )

    service = ConsumerLagService(
        event_store=event_store,
        offset_store=offset_store,
    )

    assert (
        service.lag(
            "position-service",
            "exec-001",
        )
        == 3
    )


def test_consumer_lag_without_offset_is_full_stream():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
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

    service = ConsumerLagService(
        event_store=event_store,
        offset_store=offset_store,
    )

    assert (
        service.lag(
            "position-service",
            "exec-001",
        )
        == 5
    )


def test_consumer_lag_up_to_date_is_zero():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    for sequence in range(1, 4):

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

    service = ConsumerLagService(
        event_store=event_store,
        offset_store=offset_store,
    )

    assert (
        service.lag(
            "position-service",
            "exec-001",
        )
        == 0
    )


def test_consumer_lag_empty_stream_is_zero():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    service = ConsumerLagService(
        event_store=event_store,
        offset_store=offset_store,
    )

    assert (
        service.lag(
            "position-service",
            "exec-001",
        )
        == 0
    )


def test_consumer_lag_is_isolated_per_consumer():

    event_store = (
        InMemoryExecutionEventStore()
    )

    offset_store = (
        InMemoryConsumerOffsetStore()
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
            sequence=5,
        )
    )

    offset_store.save(
        ConsumerOffset(
            consumer_id="audit-service",
            stream_id="exec-001",
            sequence=2,
        )
    )

    service = ConsumerLagService(
        event_store=event_store,
        offset_store=offset_store,
    )

    assert (
        service.lag(
            "position-service",
            "exec-001",
        )
        == 0
    )

    assert (
        service.lag(
            "audit-service",
            "exec-001",
        )
        == 3
    )
