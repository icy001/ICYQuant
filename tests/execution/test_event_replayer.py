from datetime import datetime

from services.execution.application.event_replayer import (
    ExecutionEventReplayer,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.state import (
    ExecutionState,
)


def build_partial_fill_event(
    quantity=300,
    cumulative=300,
):
    return ExecutionEvent(
        event_id=f"event-{quantity}-{cumulative}",
        execution_request_id="exec-001",
        order_id="order-001",
        event_type=ExecutionEventType.PARTIAL_FILL,
        timestamp=datetime.now(),
        filled_quantity=quantity,
        fill_price=100.0,
        cumulative_filled_quantity=cumulative,
        remaining_quantity=1000 - cumulative,
        sequence=1,
    )


def build_full_fill_event(
    quantity=300,
    cumulative=1000,
):
    return ExecutionEvent(
        event_id="event-full",
        execution_request_id="exec-001",
        order_id="order-001",
        event_type=ExecutionEventType.FILLED,
        timestamp=datetime.now(),
        filled_quantity=quantity,
        fill_price=102.0,
        cumulative_filled_quantity=cumulative,
        remaining_quantity=0,
        sequence=4,
    )


def test_execution_state_can_be_rebuilt():

    events = [
        build_partial_fill_event(
            quantity=300,
            cumulative=300,
        ),
        build_partial_fill_event(
            quantity=400,
            cumulative=700,
        ),
        build_full_fill_event(
            quantity=300,
            cumulative=1000,
        ),
    ]

    replayer = ExecutionEventReplayer()

    lifecycle, result = replayer.replay(
        events,
        requested_quantity=1000,
    )

    assert result.filled_quantity == 1000
    assert result.remaining_quantity == 0
    assert result.fully_filled

    assert (
        lifecycle.state
        == ExecutionState.FILLED
    )
