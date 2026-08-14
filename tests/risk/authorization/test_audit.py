"""Tests for the authorization audit trail (Commit 31 Part 1.4)."""

from dataclasses import FrozenInstanceError

import pytest

from services.risk.authorization.audit import (
    AuthorizationAuditRecord,
    AuthorizationAuditTrail,
    InMemoryAuthorizationAuditRepository,
    audit_record_from_event,
    new_audit_id,
)
from services.risk.authorization.events import (
    AuthorizationEventFactory,
    AuthorizationEventType,
)


@pytest.fixture
def factory() -> AuthorizationEventFactory:
    return AuthorizationEventFactory(clock=1000.0)


@pytest.fixture
def trail() -> AuthorizationAuditTrail:
    return AuthorizationAuditTrail(actor="risk-engine")


def create_lifecycle(trail: AuthorizationAuditTrail, factory: AuthorizationEventFactory):
    trail.append(factory.requested(intent_id="INT-001", correlation_id="CORR-001"))
    trail.append(
        factory.approved(
            decision_id="RISK-001",
            intent_id="INT-001",
            correlation_id="CORR-001",
            approved_quantity=100,
        )
    )
    trail.append(
        factory.issued(
            certificate_id="CERT-001",
            intent_id="INT-001",
            correlation_id="CORR-001",
        )
    )
    trail.append(
        factory.verified(
            certificate_id="CERT-001",
            intent_id="INT-001",
            correlation_id="CORR-001",
        )
    )
    trail.append(
        factory.consumed(
            certificate_id="CERT-001",
            intent_id="INT-001",
            correlation_id="CORR-001",
            order_request_id="OR-001",
        )
    )


def test_audit_record_is_immutable(factory):
    record = audit_record_from_event(
        factory.approved(decision_id="RISK-001", intent_id="INT-001"),
        actor="risk-engine",
    )
    with pytest.raises(FrozenInstanceError):
        record.reason = "changed"


def test_authorization_lifecycle_order(trail, factory):
    create_lifecycle(trail, factory)
    records = trail.get_by_intent("INT-001")
    assert [record.event_type for record in records] == [
        AuthorizationEventType.REQUESTED,
        AuthorizationEventType.APPROVED,
        AuthorizationEventType.ISSUED,
        AuthorizationEventType.VERIFIED,
        AuthorizationEventType.CONSUMED,
    ]


def test_event_sequence_is_monotonic(trail, factory):
    create_lifecycle(trail, factory)
    records = trail.get_by_intent("INT-001")
    sequences = [record.sequence for record in records]
    assert sequences == sorted(sequences)


def test_correlation_trace(trail, factory):
    create_lifecycle(trail, factory)
    records = trail.get_by_correlation("CORR-001")
    assert len(records) >= 1
    for record in records:
        assert record.correlation_id == "CORR-001"


def test_get_by_certificate(trail, factory):
    create_lifecycle(trail, factory)
    records = trail.get_by_certificate("CERT-001")
    assert len(records) == 3
    for record in records:
        assert record.certificate_id == "CERT-001"


def test_audit_record_carries_actor_and_event_id(trail, factory):
    event = factory.approved(decision_id="RISK-001", intent_id="INT-001")
    record = trail.append(event, actor="execution-service")
    assert record.actor == "execution-service"
    assert record.event_id == event.event_id
    assert record.event_type == AuthorizationEventType.APPROVED


def test_trail_default_actor():
    trail = AuthorizationAuditTrail()
    record = trail.append(
        AuthorizationEventFactory(clock=1000.0).requested(intent_id="INT-001")
    )
    assert record.actor == "system"


def test_audit_id_is_generated():
    assert new_audit_id(1000).startswith("AUD-")


def test_previous_event_id_chain_in_trail(trail, factory):
    create_lifecycle(trail, factory)
    records = trail.get_by_intent("INT-001")
    for previous, current in zip(records, records[1:]):
        assert current.previous_event_id == previous.event_id


def test_in_memory_repository_idempotent_append(trail, factory):
    event = factory.approved(decision_id="RISK-001", intent_id="INT-001")
    record = audit_record_from_event(event, actor="risk-engine")
    trail.repository.append(record)
    trail.repository.append(record)  # same audit_id -> ignored
    assert len(trail.repository.get_by_intent("INT-001")) == 1


def test_audit_record_as_dict(trail, factory):
    event = factory.approved(
        decision_id="RISK-001",
        intent_id="INT-001",
        correlation_id="CORR-001",
        approved_quantity=100,
    )
    record = audit_record_from_event(event, actor="risk-engine")
    data = record.as_dict()
    assert data["event_type"] == "APPROVED"
    assert data["actor"] == "risk-engine"
    assert data["correlation_id"] == "CORR-001"


def test_custom_repository_pluggable():
    class RecordingRepository(InMemoryAuthorizationAuditRepository):
        def __init__(self):
            super().__init__()
            self.appends = 0

        def append(self, record: AuthorizationAuditRecord) -> None:
            self.appends += 1
            super().append(record)

    repository = RecordingRepository()
    trail = AuthorizationAuditTrail(repository, actor="risk-engine")
    event = AuthorizationEventFactory(clock=1000.0).requested(intent_id="INT-001")
    trail.append(event)
    assert repository.appends == 1
