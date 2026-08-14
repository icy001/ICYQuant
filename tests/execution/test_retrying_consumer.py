from datetime import datetime

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.application.retrying_consumer import (
    RetryingExecutionConsumer,
)
from services.execution.domain.delivery import (
    DeliveryStatus,
)
from services.execution.domain.errors import (
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
from services.execution.infrastructure.memory_delivery_store import (
    InMemoryDeliveryStore,
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


class FlakyConsumer(
    ExecutionEventConsumer
):
    """前 fail_times 次失败（可重试），之后成功。"""

    def __init__(
        self,
        fail_times: int,
    ) -> None:

        self._consumer_id = (
            "position-service"
        )
        self._fail_times = fail_times
        self._failures = 0
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

        if self._failures < self._fail_times:
            self._failures += 1
            raise RetryableExecutionError(
                "transient failure"
            )


def test_success_advances_offset():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()

    consumer = RecordingConsumer(
        "position-service"
    )

    for sequence in range(1, 4):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                sequence=sequence,
            )
        )

    runner = RetryingExecutionConsumer(
        consumer=consumer,
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
    )

    last_sequence = runner.consume(
        "exec-001"
    )

    assert last_sequence == 3

    assert consumer.sequences == [
        1,
        2,
        3,
    ]

    offset = offset_store.get(
        "position-service",
        "exec-001",
    )

    assert offset.sequence == 3


def test_retryable_failure_does_not_advance_offset():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()

    consumer = FlakyConsumer(
        fail_times=100
    )

    event_store.append(
        build_event(sequence=1)
    )

    runner = RetryingExecutionConsumer(
        consumer=consumer,
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        retry_policy=RetryPolicy(
            max_attempts=3,
        ),
    )

    # 未达 max_attempts：返回 0，offset 不推进
    last_sequence = runner.consume(
        "exec-001"
    )

    assert last_sequence == 0

    offset = offset_store.get(
        "position-service",
        "exec-001",
    )

    assert offset is None

    assert (
        len(
            dead_letter_store.list(
                "position-service"
            )
        )
        == 0
    )


def test_transient_failure_recovers_on_retry():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()

    consumer = FlakyConsumer(
        fail_times=1
    )

    for sequence in range(1, 4):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                sequence=sequence,
            )
        )

    runner = RetryingExecutionConsumer(
        consumer=consumer,
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        retry_policy=RetryPolicy(
            max_attempts=3,
        ),
    )

    # 第一次：seq 1 失败，offset 停在 0
    last_sequence = runner.consume(
        "exec-001"
    )

    assert last_sequence == 0

    # 第二次：seq 1 恢复成功，继续消费 2、3
    last_sequence = runner.consume(
        "exec-001"
    )

    assert last_sequence == 3

    offset = offset_store.get(
        "position-service",
        "exec-001",
    )

    assert offset.sequence == 3

    assert (
        len(
            dead_letter_store.list(
                "position-service"
            )
        )
        == 0
    )


def test_delivery_status_tracks_dead_lettered():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()
    delivery_store = InMemoryDeliveryStore()

    event_store.append(
        build_event(sequence=1)
    )

    runner = RetryingExecutionConsumer(
        consumer=FlakyConsumer(
            fail_times=100
        ),
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        delivery_store=delivery_store,
        retry_policy=RetryPolicy(
            max_attempts=3,
        ),
    )

    runner.consume("exec-001")
    runner.consume("exec-001")
    runner.consume("exec-001")

    latest = delivery_store.latest(
        "position-service",
        "exec-001",
        1,
    )

    assert latest is not None

    assert latest.attempt == 3

    assert (
        latest.status
        == DeliveryStatus.DEAD_LETTERED
    )


def test_delivery_status_tracks_retrying():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()
    delivery_store = InMemoryDeliveryStore()

    event_store.append(
        build_event(sequence=1)
    )

    runner = RetryingExecutionConsumer(
        consumer=FlakyConsumer(
            fail_times=100
        ),
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        delivery_store=delivery_store,
        retry_policy=RetryPolicy(
            max_attempts=3,
        ),
    )

    # attempt 1 失败 → RETRYING
    runner.consume("exec-001")

    latest = delivery_store.latest(
        "position-service",
        "exec-001",
        1,
    )

    assert latest is not None

    assert latest.attempt == 1

    assert (
        latest.status
        == DeliveryStatus.RETRYING
    )

    assert latest.error is not None


def test_delivery_status_tracks_delivered():

    event_store = InMemoryExecutionEventStore()
    offset_store = InMemoryConsumerOffsetStore()
    dead_letter_store = InMemoryDeadLetterStore()
    delivery_store = InMemoryDeliveryStore()

    event_store.append(
        build_event(sequence=1)
    )

    runner = RetryingExecutionConsumer(
        consumer=RecordingConsumer(
            "position-service"
        ),
        event_store=event_store,
        offset_store=offset_store,
        dead_letter_store=dead_letter_store,
        delivery_store=delivery_store,
    )

    runner.consume("exec-001")

    latest = delivery_store.latest(
        "position-service",
        "exec-001",
        1,
    )

    assert latest is not None

    assert (
        latest.status
        == DeliveryStatus.DELIVERED
    )
