"""Outbox idempotency tests (Commit 33 Part 1.5 #8 / #11)."""

from __future__ import annotations

import pytest

from services.order.engine.outbox.errors import DuplicateEventError
from services.order.engine.outbox.model import OutboxStatus


def test_duplicate_event_id_rejected(service, make_envelope):
    service.stage(make_envelope())
    with pytest.raises(DuplicateEventError):
        service.stage(make_envelope())


def test_duplicate_message_id_rejected(repository, make_message):
    repository.append(make_message(message_id="MSG-001", event_id="EVT-001"))
    with pytest.raises(DuplicateEventError):
        repository.append(make_message(message_id="MSG-001", event_id="EVT-002"))


def test_repeated_dispatch_does_not_republish(
    service,
    repository,
    publisher,
    dispatcher,
    make_envelope,
):
    service.stage(make_envelope())
    assert dispatcher.dispatch_once() == 1
    assert dispatcher.dispatch_once() == 0
    assert len(publisher.published_messages) == 1


def test_consumer_idempotency_boundary(
    service,
    repository,
    publisher,
    dispatcher,
    recovery,
    make_envelope,
):
    # at-least-once delivery: the bus received the event but the ack was lost
    # before mark_published -> recovery re-dispatches the SAME event_id, so
    # consumers must dedupe by event_id (#11).
    service.stage(make_envelope())
    for message in repository.pending():
        repository.mark_processing(message.message_id)
        publisher.publish(message)
        # crash: no mark_published
    assert recovery.recover() == 1
    assert dispatcher.dispatch_once() == 1

    ids = [message.event_id for message in publisher.published_messages]
    assert ids == ["EVT-ORD-000001", "EVT-ORD-000001"]
    assert len(set(ids)) == 1  # same fact delivered twice
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PUBLISHED


def test_append_never_creates_copy(repository, make_message):
    repository.append(make_message(event_id="EVT-001", message_id="MSG-001"))
    with pytest.raises(DuplicateEventError):
        repository.append(make_message(event_id="EVT-001", message_id="MSG-002"))
    assert len(list(repository.unpublished())) == 1
