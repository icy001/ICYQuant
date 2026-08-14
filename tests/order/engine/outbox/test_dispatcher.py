"""Outbox dispatcher tests (Commit 33 Part 1.5 #5 / #11)."""

from __future__ import annotations

from services.order.engine.outbox.model import OutboxStatus


def test_dispatch_publishes_pending(dispatcher, repository, publisher, make_message):
    repository.append(make_message())
    assert dispatcher.dispatch_once() == 1
    assert len(publisher.published_messages) == 1
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PUBLISHED


def test_dispatch_preserves_order(dispatcher, repository, publisher, make_message):
    for index in range(3):
        repository.append(
            make_message(message_id=f"M{index}", event_id=f"E{index}")
        )
    dispatcher.dispatch_once()
    assert [message.message_id for message in publisher.published_messages] == [
        "M0",
        "M1",
        "M2",
    ]


def test_dispatch_second_round_is_noop(dispatcher, repository, publisher, make_message):
    repository.append(make_message())
    assert dispatcher.dispatch_once() == 1
    assert dispatcher.dispatch_once() == 0
    assert len(publisher.published_messages) == 1


def test_dispatch_marks_failed_on_publish_error(
    dispatcher,
    repository,
    publisher,
    make_message,
):
    repository.append(make_message())
    publisher.fail_on_publish = True
    assert dispatcher.dispatch_once() == 0
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.FAILED
    assert message.last_error is not None
    assert "unavailable" in message.last_error
    assert publisher.published_messages == []


def test_dispatch_nothing_pending_returns_zero(dispatcher, repository):
    assert dispatcher.dispatch_once() == 0


def test_dispatch_limits_batch(dispatcher, repository, publisher, make_message):
    for index in range(5):
        repository.append(
            make_message(message_id=f"M{index}", event_id=f"E{index}")
        )
    assert dispatcher.dispatch_once(limit=2) == 2
    assert len(publisher.published_messages) == 2
    assert len(list(repository.pending())) == 3
