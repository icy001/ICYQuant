"""Outbox service tests (Commit 33 Part 1.5 #4)."""

from __future__ import annotations

import pytest

from services.order.engine.outbox.errors import DuplicateEventError
from services.order.engine.outbox.model import OutboxStatus


def test_stage_persists_message(service, repository, make_envelope):
    message = service.stage(make_envelope())
    assert repository.get("EVT-ORD-000001") == message
    assert message.status is OutboxStatus.PENDING
    assert message.retry_count == 0


def test_stage_uses_event_id_as_message_id(service, make_envelope):
    message = service.stage(make_envelope(sequence=1))
    assert message.message_id == "EVT-ORD-000001"
    assert message.event_id == "EVT-ORD-000001"


def test_stage_preserves_lineage(service, make_envelope):
    message = service.stage(
        make_envelope(
            event_id="EVT-ORD-000007",
            sequence=7,
            aggregate_id="ORD-20260813-000099",
            aggregate_type="ORDER",
            order_id="ORD-20260813-000099",
            order_request_id="OR-20260813-000099",
            correlation_id="CORR-007",
            causation_id="CMD-001",
        )
    )
    assert message.aggregate_id == "ORD-20260813-000099"
    assert message.aggregate_type == "ORDER"
    assert message.aggregate_version == 7
    assert message.correlation_id == "CORR-007"
    assert message.causation_id == "CMD-001"


def test_stage_preserves_payload(service, make_envelope):
    message = service.stage(make_envelope(payload={"venue_order_id": "VENUE-000001"}))
    assert message.payload == {"venue_order_id": "VENUE-000001"}


def test_stage_duplicate_event_raises(service, make_envelope):
    service.stage(make_envelope())
    with pytest.raises(DuplicateEventError):
        service.stage(make_envelope())
