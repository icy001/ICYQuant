"""Outbox recovery tests (Commit 33 Part 1.5 #7 / #11)."""

from __future__ import annotations

from services.order.engine.outbox.model import OutboxStatus


def test_recover_failed_event(repository, recovery, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    repository.mark_failed("EVT-ORD-000001", "bus down")
    assert recovery.recover() == 1
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PENDING


def test_recover_processing_message(repository, recovery, make_message):
    # a dispatcher crash left the message in PROCESSING
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    assert recovery.recover() == 1
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PENDING


def test_recover_skips_published(repository, recovery, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    repository.mark_published("EVT-ORD-000001")
    assert recovery.recover() == 0
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PUBLISHED


def test_recover_skips_exhausted(repository, recovery, make_message):
    repository.append(make_message(retry_count=5))
    repository.mark_processing("EVT-ORD-000001")
    assert recovery.recover() == 0
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PROCESSING


def test_event_bus_down_then_recovery_and_retry(
    service,
    repository,
    publisher,
    dispatcher,
    recovery,
    make_envelope,
):
    # #11 Event Bus Down: PENDING -> FAILED -> Recovery -> Retry -> PUBLISHED
    service.stage(make_envelope())
    publisher.fail_on_publish = True
    assert dispatcher.dispatch_once() == 0
    assert repository.get("EVT-ORD-000001").status is OutboxStatus.FAILED

    # bus comes back
    publisher.fail_on_publish = False
    assert recovery.recover() == 1
    assert dispatcher.dispatch_once() == 1
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PUBLISHED
    assert len(publisher.published_messages) == 1
