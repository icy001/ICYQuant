from datetime import datetime

import pytest

from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.infrastructure.memory_event_store import (
    InMemoryExecutionEventStore,
)


def build_event(
    event_id="event-001",
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


def test_events_must_have_contiguous_sequence():

    store = (
        InMemoryExecutionEventStore()
    )

    event_1 = build_event(
        event_id="event-001",
        request_id="exec-001",
        sequence=1,
    )

    event_2 = build_event(
        event_id="event-002",
        request_id="exec-001",
        sequence=2,
    )

    store.append(event_1)
    store.append(event_2)

    assert (
        store.latest_sequence(
            "exec-001"
        )
        == 2
    )


def test_sequence_gap_is_rejected():

    store = (
        InMemoryExecutionEventStore()
    )

    store.append(
        build_event(
            event_id="event-001",
            request_id="exec-001",
            sequence=1,
        )
    )

    with pytest.raises(ValueError):

        store.append(
            build_event(
                event_id="event-003",
                request_id="exec-001",
                sequence=3,
            )
        )


def test_stream_after_sequence():

    store = (
        InMemoryExecutionEventStore()
    )

    for sequence in range(1, 5):

        store.append(
            build_event(
                event_id=(
                    f"event-{sequence:03d}"
                ),
                request_id="exec-001",
                sequence=sequence,
            )
        )

    events = store.stream(
        "exec-001",
        after_sequence=2,
    )

    assert [
        event.sequence
        for event in events
    ] == [3, 4]
