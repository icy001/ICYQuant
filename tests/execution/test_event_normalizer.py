from datetime import datetime

from services.execution.application.event_normalizer import (
    ExecutionEventNormalizer,
)
from services.execution.domain.event import (
    ExecutionEventType,
)
from services.execution.domain.fill import (
    ExecutionFill,
)


def test_partial_fill_normalization():

    normalizer = ExecutionEventNormalizer()

    fill = ExecutionFill(
        execution_id="fill-001",
        execution_request_id="exec-001",
        order_id="order-001",
        quantity=300,
        price=100,
        timestamp=datetime.now(),
    )

    event = normalizer.fill_to_event(
        fill,
        requested_quantity=1000,
        cumulative_quantity=300,
    )

    assert (
        event.event_type
        == ExecutionEventType.PARTIAL_FILL
    )

    assert event.filled_quantity == 300

    assert (
        event.remaining_quantity
        == 700
    )


def test_full_fill_normalization():

    normalizer = ExecutionEventNormalizer()

    fill = ExecutionFill(
        execution_id="fill-002",
        execution_request_id="exec-001",
        order_id="order-001",
        quantity=1000,
        price=101,
        timestamp=datetime.now(),
    )

    event = normalizer.fill_to_event(
        fill,
        requested_quantity=1000,
        cumulative_quantity=1000,
    )

    assert (
        event.event_type
        == ExecutionEventType.FILLED
    )

    assert (
        event.remaining_quantity
        == 0
    )
