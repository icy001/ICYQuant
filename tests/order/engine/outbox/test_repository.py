"""Outbox repository tests (Commit 33 Part 1.5 #3 / #8)."""

from __future__ import annotations

import pytest

from services.order.engine.outbox.errors import (
    DuplicateEventError,
    OutboxMessageNotFoundError,
    OutboxPersistenceError,
)
from services.order.engine.outbox.model import OutboxStatus


def test_append_and_get_roundtrip(repository, make_message):
    message = make_message()
    repository.append(message)
    assert repository.get("EVT-ORD-000001") == message


def test_get_missing_returns_none(repository):
    assert repository.get("EVT-ORD-999999") is None


def test_append_duplicate_event_id_raises(repository, make_message):
    repository.append(make_message(event_id="EVT-001", message_id="MSG-001"))
    with pytest.raises(DuplicateEventError):
        repository.append(make_message(event_id="EVT-001", message_id="MSG-002"))


def test_append_duplicate_message_id_raises(repository, make_message):
    repository.append(make_message(message_id="MSG-001", event_id="EVT-001"))
    with pytest.raises(DuplicateEventError):
        repository.append(make_message(message_id="MSG-001", event_id="EVT-002"))


def test_pending_only_returns_pending(repository, make_message):
    repository.append(make_message(message_id="M1", event_id="E1"))
    repository.append(
        make_message(message_id="M2", event_id="E2", status=OutboxStatus.FAILED)
    )
    pending = list(repository.pending())
    assert [message.message_id for message in pending] == ["M1"]


def test_pending_respects_limit(repository, make_message):
    for index in range(3):
        repository.append(
            make_message(message_id=f"M{index}", event_id=f"E{index}")
        )
    assert len(list(repository.pending(limit=2))) == 2


def test_mark_processing(repository, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PROCESSING
    assert list(repository.pending()) == []


def test_mark_published(repository, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    repository.mark_published("EVT-ORD-000001")
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PUBLISHED
    assert message.published_at is not None


def test_mark_failed_increments_retry(repository, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    repository.mark_failed("EVT-ORD-000001", "bus down")
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.FAILED
    assert message.last_error == "bus down"
    assert message.retry_count == 1


def test_mark_missing_message_raises(repository):
    with pytest.raises(OutboxMessageNotFoundError):
        repository.mark_processing("EVT-ORD-999999")


def test_fail_on_append_is_fail_closed(repository, make_message):
    repository.fail_on_append = True
    with pytest.raises(OutboxPersistenceError):
        repository.append(make_message())


def test_unpublished_returns_unfinished(repository, make_message):
    repository.append(make_message(message_id="M1", event_id="E1"))
    repository.append(
        make_message(message_id="M2", event_id="E2", status=OutboxStatus.PUBLISHED)
    )
    repository.append(
        make_message(message_id="M3", event_id="E3", status=OutboxStatus.FAILED)
    )
    assert [message.message_id for message in repository.unpublished()] == [
        "M1",
        "M3",
    ]


def test_reset_pending_clears_error(repository, make_message):
    repository.append(make_message())
    repository.mark_processing("EVT-ORD-000001")
    repository.mark_failed("EVT-ORD-000001", "boom")
    repository.reset_pending("EVT-ORD-000001")
    message = repository.get("EVT-ORD-000001")
    assert message is not None
    assert message.status is OutboxStatus.PENDING
    assert message.last_error is None
