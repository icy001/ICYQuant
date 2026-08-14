"""Outbox message model tests (Commit 33 Part 1.5 #2 / #9)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.order.engine.outbox.model import (
    OutboxStatus,
    validate_version,
)


def test_outbox_message_defaults(make_message):
    message = make_message()
    assert message.status is OutboxStatus.PENDING
    assert message.retry_count == 0
    assert message.last_error is None
    assert message.published_at is None


def test_outbox_message_identity_fields(make_message):
    message = make_message(
        message_id="MSG-001",
        event_id="EVT-001",
        aggregate_id="ORD-001",
        aggregate_version=3,
    )
    assert message.message_id == "MSG-001"
    assert message.event_id == "EVT-001"
    assert message.aggregate_id == "ORD-001"
    assert message.aggregate_version == 3


def test_outbox_message_is_immutable(make_message):
    message = make_message()
    with pytest.raises(FrozenInstanceError):
        message.status = OutboxStatus.PUBLISHED  # type: ignore[misc]


def test_outbox_message_requires_message_id(make_message):
    with pytest.raises(ValueError):
        make_message(message_id="")


def test_outbox_message_requires_aggregate_version(make_message):
    with pytest.raises(ValueError):
        make_message(aggregate_version=0)


def test_outbox_message_rejects_negative_retry_count(make_message):
    with pytest.raises(ValueError):
        make_message(retry_count=-1)


def test_validate_version_accepts_next():
    validate_version(1, 2)  # v1 -> v2 is legal


def test_validate_version_rejects_jump():
    with pytest.raises(ValueError, match="invalid aggregate event version"):
        validate_version(1, 3)


def test_validate_version_rejects_repeat():
    with pytest.raises(ValueError, match="invalid aggregate event version"):
        validate_version(2, 2)


def test_status_enum_values():
    assert OutboxStatus.PENDING.value == "PENDING"
    assert OutboxStatus.PROCESSING.value == "PROCESSING"
    assert OutboxStatus.PUBLISHED.value == "PUBLISHED"
    assert OutboxStatus.FAILED.value == "FAILED"
