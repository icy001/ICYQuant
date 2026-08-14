from datetime import datetime

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.application.retrying_consumer import (
    RetryingExecutionConsumer,
)
from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)
from services.execution.domain.errors import (
    NonRetryableExecutionError,
    RetryableExecutionError,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.retry import (
    RetryPolicy,
)
from services.execution.infrastructure.memory_consumer_offset_store import (
    InMemoryConsumerOffsetStore,
)
from services.execution.infrastructure.memory_dead_letter_store import (
    InMemoryDeadLetterStore,
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


def test_failed_event_goes_to_dead_letter():

    store = InMemoryDeadLetterStore()

    event = build_event(
        event_id="event-100",
        request_id="exec-001",
        sequence=100,
    )

    dead_letter = DeadLetterEvent(
        event=event,
        consumer_id="position-service",
        attempts=3,
        error="database unavailable",
        created_at=datetime.now(),
    )

    store.save(dead_letter)

    items = store.list(
        "position-service"
    )

    assert len(items) == 1

    assert (
        items[0].attempts
        == 3
    )


def test_dead_letter_list_without_filter():

    store = InMemoryDeadLetterStore()

    store.save(
        DeadLetterEvent(
            event=build_event(sequence=1),
            consumer_id="position-service",
            attempts=2,
            error="timeout",
            created_at=datetime.now(),
        )
    )

    store.save(
        DeadLetterEvent(
            event=build_event(sequence=2),
            consumer_id="ledger-service",
            attempts=4,
            error="timeout",
            created_at=datetime.now(),
        )
    )

    assert len(store.list()) == 2

    assert (
        len(store.list("position-service"))
        == 1
    )

    assert (
        len(store.list("ledger-service"))
        == 1
    )


def test_dead_letter_validation():

    store = InMemoryDeadLetterStore()

    import pytest

    with pytest.raises(ValueError):
        store.save(
            DeadLetterEvent(
                event=build_event(sequence=1),
                consumer_id="",
                attempts=3,
                error="database unavailable",
                created_at=datetime.now(),
            )
        )

    with pytest.raises(ValueError):
        store.save(
            DeadLetterEvent(
                event=build_event(sequence=1),
                consumer_id="position-service",
                attempts=0,
                error="database unavailable",
                created_at=datetime.now(),
            )
        )

    with pytest.raises(ValueError):
        store.save(
            DeadLetterEvent(
                event=build_event(sequence=1),
                consumer_id="position-service",
                attempts=3,
                error="",
                created_at=datetime.now(),
            )
        )


class NonRetryableConsumer(
    ExecutionEventConsumer
):

    @property
    def consumer_id(self):
        return "position-service"

    def handle(self, event):
        raise NonRetryableExecutionError(
            "invalid event schema"
        )


def test_non_retryable_error_is_dead_lettered():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()

    event_store.append(
        build_event(
            event_id="event-102",
            request_id="exec-001",
            sequence=1,
        )
    )

    runner = RetryingExecutionConsumer(
        consumer=NonRetryableConsumer(),
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        retry_policy=RetryPolicy(
            max_attempts=5,
        ),
    )

    last_sequence = runner.consume(
        "exec-001"
    )

    # 非重试错误：立即 Dead Letter，不推进 offset
    assert last_sequence == 0

    items = dead_letter_store.list(
        "position-service"
    )

    assert len(items) == 1

    assert items[0].attempts == 1

    assert (
        items[0].error
        == "invalid event schema"
    )


class RetryableFailingConsumer(
    ExecutionEventConsumer
):

    @property
    def consumer_id(self):
        return "position-service"

    def handle(self, event):
        raise RetryableExecutionError(
            "database timeout"
        )


def test_retryable_error_reaches_max_attempts_then_dead_letter():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()

    event_store.append(
        build_event(
            event_id="event-103",
            request_id="exec-001",
            sequence=1,
        )
    )

    runner = RetryingExecutionConsumer(
        consumer=RetryableFailingConsumer(),
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        retry_policy=RetryPolicy(
            max_attempts=3,
        ),
    )

    # 连续调用：attempt 1、2 均失败但不到上限，第 3 次达上限 → Dead Letter
    runner.consume("exec-001")
    runner.consume("exec-001")
    last_sequence = runner.consume(
        "exec-001"
    )

    assert last_sequence == 0

    items = dead_letter_store.list(
        "position-service"
    )

    assert len(items) == 1

    assert items[0].attempts == 3
