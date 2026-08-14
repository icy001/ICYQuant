"""Commit 39 Part 1.4 E2E smoke (temporary, deleted after run)."""
from datetime import datetime

from services.execution.application.event_consumer import ExecutionEventConsumer
from services.execution.application.retrying_consumer import RetryingExecutionConsumer
from services.execution.domain.delivery import DeliveryStatus
from services.execution.domain.errors import (
    NonRetryableExecutionError,
    RetryableExecutionError,
)
from services.execution.domain.event import ExecutionEvent, ExecutionEventType
from services.execution.domain.retry import RetryPolicy
from services.execution.infrastructure.memory_consumer_offset_store import InMemoryConsumerOffsetStore
from services.execution.infrastructure.memory_dead_letter_store import InMemoryDeadLetterStore
from services.execution.infrastructure.memory_delivery_store import InMemoryDeliveryStore
from services.execution.infrastructure.memory_event_store import InMemoryExecutionEventStore


def build_event(event_id, sequence):
    return ExecutionEvent(
        event_id=event_id,
        execution_request_id="exec-001",
        order_id="order-001",
        event_type=ExecutionEventType.FILLED,
        timestamp=datetime.now(),
        sequence=sequence,
    )


class FlakyPositionConsumer(ExecutionEventConsumer):
    """Position: fails once on seq 1 (transient), then OK."""

    def __init__(self):
        self._failed = False
        self.handled = []

    @property
    def consumer_id(self):
        return "position-service"

    def handle(self, event):
        self.handled.append(event.sequence)
        if event.sequence == 1 and not self._failed:
            self._failed = True
            raise RetryableExecutionError("position db timeout")


class BadAuditConsumer(ExecutionEventConsumer):
    """Audit: always non-retryable schema error."""

    @property
    def consumer_id(self):
        return "audit-service"

    def handle(self, event):
        raise NonRetryableExecutionError("invalid event schema")


def main():
    event_store = InMemoryExecutionEventStore()
    for seq in (1, 2, 3):
        event_store.append(build_event(f"event-{seq}", seq))

    # --- Position: transient failure -> retry -> recover ---
    pos_offset = InMemoryConsumerOffsetStore()
    pos_dlq = InMemoryDeadLetterStore()
    pos_delivery = InMemoryDeliveryStore()
    pos = FlakyPositionConsumer()
    runner = RetryingExecutionConsumer(
        consumer=pos,
        event_store=event_store,
        offset_store=pos_offset,
        dead_letter_store=pos_dlq,
        delivery_store=pos_delivery,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    last = runner.consume("exec-001")
    assert last == 0, last
    assert pos_offset.get("position-service", "exec-001") is None
    st = pos_delivery.latest("position-service", "exec-001", 1)
    assert st.status == DeliveryStatus.RETRYING, st

    last = runner.consume("exec-001")
    assert last == 3, last
    assert pos_offset.get("position-service", "exec-001").sequence == 3
    assert pos.handled == [1, 1, 2, 3]
    assert pos_dlq.list("position-service") == []

    # --- Audit: non-retryable -> dead letter on attempt 1, no offset ---
    audit_offset = InMemoryConsumerOffsetStore()
    audit_dlq = InMemoryDeadLetterStore()
    audit_delivery = InMemoryDeliveryStore()
    audit = BadAuditConsumer()
    runner = RetryingExecutionConsumer(
        consumer=audit,
        event_store=event_store,
        offset_store=audit_offset,
        dead_letter_store=audit_dlq,
        delivery_store=audit_delivery,
        retry_policy=RetryPolicy(max_attempts=5),
    )
    last = runner.consume("exec-001")
    assert last == 0, last
    dlq = audit_dlq.list("audit-service")
    assert len(dlq) == 1 and dlq[0].attempts == 1
    st = audit_delivery.latest("audit-service", "exec-001", 1)
    assert st.status == DeliveryStatus.DEAD_LETTERED and st.attempt == 1

    # --- Isolation: position offset unaffected by audit failure ---
    assert pos_offset.get("position-service", "exec-001").sequence == 3

    print("SMOKE PART 1.4 OK")


if __name__ == "__main__":
    main()
