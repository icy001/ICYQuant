"""Tests for authorization lifecycle events (Commit 31 Part 1.4)."""

from dataclasses import FrozenInstanceError
from typing import Optional

import pytest

from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
from services.risk.authorization.events import (
    AuthorizationEvent,
    AuthorizationEventFactory,
    AuthorizationEventMetadata,
    AuthorizationEventType,
    new_event_id,
)


def make_certificate(**overrides) -> ExecutionAuthorizationCertificate:
    defaults = dict(
        certificate_id="CERT-001",
        authorization_id="AUTH-001",
        decision_id="RISK-001",
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        approved=True,
        approved_quantity=100.0,
        issued_at=1000.0,
        expires_at=1005.0,
        symbol="NVDA",
        side="BUY",
        execution_policy="LIMIT",
    )
    defaults.update(overrides)
    return ExecutionAuthorizationCertificate(**defaults)


@pytest.fixture
def factory() -> AuthorizationEventFactory:
    return AuthorizationEventFactory(clock=1000.0)


def test_approved_event_contains_decision(factory):
    event = factory.approved(
        decision_id="RISK-001",
        intent_id="INT-001",
        approved_quantity=100,
    )
    assert event.event_type == AuthorizationEventType.APPROVED
    assert event.decision_id == "RISK-001"
    assert event.intent_id == "INT-001"
    assert event.approved_quantity == 100


def test_rejected_event_contains_reason(factory):
    event = factory.rejected(
        decision_id="RISK-002",
        intent_id="INT-002",
        reason="EXPOSURE_LIMIT",
    )
    assert event.event_type == AuthorizationEventType.REJECTED
    assert event.reason == "EXPOSURE_LIMIT"


def test_event_is_immutable(factory):
    event = factory.requested(intent_id="INT-001")
    with pytest.raises(FrozenInstanceError):
        event.reason = "changed"


def test_event_id_is_generated(factory):
    event = factory.requested(intent_id="INT-001")
    assert event.event_id.startswith("EVT-")
    assert new_event_id(1000).startswith("EVT-")


def test_event_types_enum_values():
    assert AuthorizationEventType.REQUESTED.value == "REQUESTED"
    assert AuthorizationEventType.APPROVED.value == "APPROVED"
    assert AuthorizationEventType.REJECTED.value == "REJECTED"
    assert AuthorizationEventType.ISSUED.value == "ISSUED"
    assert AuthorizationEventType.VERIFIED.value == "VERIFIED"
    assert AuthorizationEventType.CONSUMED.value == "CONSUMED"
    assert AuthorizationEventType.EXPIRED.value == "EXPIRED"


def test_requested_event_identity(factory):
    event = factory.requested(
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
    )
    assert event.event_type == AuthorizationEventType.REQUESTED
    assert event.strategy_id == "STRAT-001"
    assert event.session_id == "SESSION-001"
    assert event.signal_id == "SIG-001"
    assert event.correlation_id == "CORR-001"


def test_issued_event_carries_certificate(factory):
    event = factory.issued_from_certificate(make_certificate())
    assert event.event_type == AuthorizationEventType.ISSUED
    assert event.certificate_id == "CERT-001"
    assert event.authorization_id == "AUTH-001"
    assert event.decision_id == "RISK-001"
    assert event.approved_quantity == 100.0


def test_consumed_event_carries_order_request(factory):
    event = factory.consumed_from_certificate(
        make_certificate(),
        order_request_id="OR-001",
    )
    assert event.event_type == AuthorizationEventType.CONSUMED
    assert event.order_request_id == "OR-001"


def test_verified_event_carries_certificate(factory):
    event = factory.verified_from_certificate(make_certificate())
    assert event.event_type == AuthorizationEventType.VERIFIED
    assert event.certificate_id == "CERT-001"
    assert event.intent_id == "INT-001"


def test_expired_event_carries_certificate(factory):
    event = factory.expired_from_certificate(make_certificate())
    assert event.event_type == AuthorizationEventType.EXPIRED
    assert event.certificate_id == "CERT-001"
    assert event.authorization_id == "AUTH-001"


def test_sequence_is_monotonic_per_correlation(factory):
    events = [
        factory.approved(intent_id="INT-001", correlation_id="CORR-001"),
        factory.issued(certificate_id="CERT-001", correlation_id="CORR-001"),
        factory.verified(certificate_id="CERT-001", correlation_id="CORR-001"),
    ]
    sequences = [event.sequence for event in events]
    assert sequences == [1, 2, 3]
    assert sequences == sorted(sequences)


def test_sequence_resets_per_correlation(factory):
    first = factory.approved(intent_id="INT-001", correlation_id="CORR-001")
    second = factory.approved(intent_id="INT-002", correlation_id="CORR-002")
    assert first.sequence == 1
    assert second.sequence == 1


def test_previous_event_id_links_chain(factory):
    first = factory.approved(intent_id="INT-001", correlation_id="CORR-001")
    second = factory.issued(certificate_id="CERT-001", correlation_id="CORR-001")
    third = factory.verified(certificate_id="CERT-001", correlation_id="CORR-001")
    assert first.previous_event_id is None
    assert second.previous_event_id == first.event_id
    assert third.previous_event_id == second.event_id


def test_metadata_defaults():
    metadata = AuthorizationEventMetadata()
    assert metadata.source == "risk.authorization"
    assert metadata.version == "1"
    assert metadata.environment == "production"


def test_metadata_custom():
    metadata = AuthorizationEventMetadata(
        source="risk.authorization",
        version="2",
        environment="staging",
    )
    assert metadata.version == "2"
    assert metadata.environment == "staging"


def test_occurred_at_uses_clock_when_not_supplied(factory):
    event = factory.requested(intent_id="INT-001")
    assert event.occurred_at == 1000.0


def test_occurred_at_override(factory):
    event = factory.requested(intent_id="INT-001", occurred_at=1234.5)
    assert event.occurred_at == 1234.5


def test_rejected_from_decision_uses_decision_reason(factory):
    event = factory.rejected(
        decision_id="RISK-002",
        intent_id="INT-002",
        correlation_id="CORR-002",
        reason="EXPOSURE_LIMIT",
    )
    assert event.reason == "EXPOSURE_LIMIT"
    assert event.correlation_id == "CORR-002"


def test_event_has_lineage_fields(factory):
    event: Optional[AuthorizationEvent] = factory.approved(
        decision_id="RISK-001",
        intent_id="INT-001",
        correlation_id="CORR-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        authorization_id="AUTH-001",
    )
    assert event.authorization_id == "AUTH-001"
    assert event.decision_id == "RISK-001"
    assert event.strategy_id == "STRAT-001"
