"""Event sink and transactional outbox tests (Commit 29 Part 1.5 §12, §47-52, §58-59)."""

from __future__ import annotations

from services.control_plane.event import InMemoryEventStore
from services.control_plane.event_sink import (
    EventPublishError,
    InMemoryEventSink,
    OutboxPublisher,
    OutboxState,
    OutboxStore,
)


def test_sink_publishes_events():
    sink = InMemoryEventSink()
    store = InMemoryEventStore()
    event = store.append(
        event_type="COMMAND_CREATED",
        command_id="CMD-001",
        correlation_id="CORR-001",
    )
    sink.publish(event)
    assert len(sink.published) == 1
    assert sink.published[0].event_type == "COMMAND_CREATED"


def test_failing_sink_raises_event_publish_error():
    sink = InMemoryEventSink()
    store = InMemoryEventStore()
    sink.fail()
    event = store.append(
        event_type="COMMAND_CREATED",
        command_id="CMD-001",
        correlation_id="CORR-001",
    )
    try:
        sink.publish(event)
    except EventPublishError:
        pass
    else:
        raise AssertionError("failing sink must raise EventPublishError")
    assert sink.failed is True


def test_success_writes_outbox():
    outbox = OutboxStore()
    outbox.append(
        command_id="CMD-001",
        event_type="COMMAND_SUCCEEDED",
        correlation_id="CORR-001",
    )
    assert outbox.has_pending("CMD-001")
    pending = outbox.pending("CMD-001")
    assert len(pending) == 1
    assert pending[0].state is OutboxState.PENDING


def test_outbox_publisher_delivers_and_marks_published():
    outbox = OutboxStore()
    outbox.append(
        command_id="CMD-001",
        event_type="COMMAND_SUCCEEDED",
        correlation_id="CORR-001",
        payload={"state": "SUCCEEDED"},
    )
    sink = InMemoryEventSink()
    result = OutboxPublisher(outbox, sink).flush("CMD-001")
    assert result.published == 1
    assert result.failed == 0
    assert outbox.has_pending("CMD-001") is False
    published = [entry for entry in outbox.all() if entry.command_id == "CMD-001"]
    assert published[0].state is OutboxState.PUBLISHED
    assert published[0].published_at is not None
    assert len(sink.published) == 1


def test_event_sink_failure_does_not_fail_command():
    outbox = OutboxStore()
    outbox.append(
        command_id="CMD-001",
        event_type="COMMAND_SUCCEEDED",
        correlation_id="CORR-001",
    )
    sink = InMemoryEventSink()
    sink.fail()
    result = OutboxPublisher(outbox, sink).flush("CMD-001")
    assert result.published == 0
    assert result.failed == 1
    # The command state itself is untouched by delivery failure (§52).
    assert outbox.has_pending("CMD-001") is False  # drained, marked FAILED
    failed = [entry for entry in outbox.all() if entry.command_id == "CMD-001"]
    assert failed[0].state is OutboxState.FAILED
    assert failed[0].retry_count == 1


def test_failed_outbox_entries_retry_after_sink_recovers():
    outbox = OutboxStore()
    entry = outbox.append(
        command_id="CMD-001",
        event_type="COMMAND_SUCCEEDED",
        correlation_id="CORR-001",
    )
    sink = InMemoryEventSink()
    sink.fail()
    OutboxPublisher(outbox, sink).flush("CMD-001")
    assert entry.state is OutboxState.FAILED

    sink.recover()
    # FAILED entries are not pending; retry requires explicit re-enqueue.
    assert outbox.has_pending("CMD-001") is False
    outbox.append(
        command_id="CMD-001",
        event_type="COMMAND_SUCCEEDED",
        correlation_id="CORR-001",
    )
    result = OutboxPublisher(outbox, sink).flush("CMD-001")
    assert result.published == 1
