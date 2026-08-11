"""
Test AuditEngine — immutable audit event recording and query.
"""

import time
import pytest

from services.governance.audit_event_type import AuditEventType
from services.governance.audit_actor import AuditActor, ActorType
from services.governance.audit_action import AuditAction
from services.governance.audit_outcome import AuditOutcome
from services.governance.audit_context import AuditContext
from services.governance.audit_event import AuditEvent
from services.governance.audit_engine import AuditEngine
from services.governance.immutable_audit_log import ImmutableAuditLog
from services.governance.audit_chain import AuditChain


class TestAuditEvent:
    """Test AuditEvent creation and immutability."""

    def test_create_audit_event(self):
        actor = AuditActor.human("user-001", "Alice", "AUTH-001")
        event = AuditEvent(
            event_id="AEVT-TEST001",
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="DECISION",
            entity_id="DEC-001",
            actor=actor,
            action=AuditAction.CREATE,
            reason="Test event",
        )
        assert event.event_id == "AEVT-TEST001"
        assert event.event_type == AuditEventType.DECISION_CREATED
        assert event.actor.actor_id == "user-001"

    def test_immutability(self):
        actor = AuditActor.human("user-001")
        event = AuditEvent(
            event_id="AEVT-TEST002",
            event_type=AuditEventType.POLICY_PUBLISHED,
            entity_type="POLICY",
            entity_id="POL-001",
            actor=actor,
            action=AuditAction.PUBLISH,
        )
        with pytest.raises(AttributeError, match="immutable"):
            event.event_id = "CHANGED"

    def test_to_dict_from_dict(self):
        actor = AuditActor.human("user-001", "Alice")
        event = AuditEvent(
            event_id="AEVT-TEST003",
            event_type=AuditEventType.APPROVAL_APPROVED,
            entity_type="APPROVAL",
            entity_id="APR-001",
            actor=actor,
            action=AuditAction.APPROVE,
            outcome=AuditOutcome.APPROVAL_GRANTED,
            reason="Approved by Alice",
            correlation_id="CORR-TEST",
        )
        event_data = event.to_dict()
        restored = AuditEvent.from_dict(event_data)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.actor.actor_id == "user-001"
        assert restored.correlation_id == "CORR-TEST"


class TestImmutableAuditLog:
    """Test ImmutableAuditLog append-only behavior."""

    def test_record_and_query(self):
        log = ImmutableAuditLog(max_events=100)
        actor = AuditActor.system("test-service", "1.0")

        for i in range(5):
            event = AuditEvent(
                event_id=f"AEVT-{i:04d}",
                event_type=AuditEventType.DECISION_CREATED,
                entity_type="DECISION",
                entity_id=f"DEC-{i:03d}",
                actor=actor,
                action=AuditAction.CREATE,
                correlation_id="CORR-TEST",
            )
            log.record(event)

        assert log.size == 5
        corr_events = log.query_by_correlation("CORR-TEST")
        assert len(corr_events) == 5

    def test_query_by_entity(self):
        log = ImmutableAuditLog(max_events=100)
        actor = AuditActor.system("test")

        for i in range(3):
            event = AuditEvent(
                event_id=f"AEVT-E-{i}",
                event_type=AuditEventType.POLICY_PUBLISHED,
                entity_type="POLICY",
                entity_id="POL-001",
                actor=actor,
                action=AuditAction.PUBLISH,
            )
            log.record(event)

        results = log.query_by_entity("POLICY", "POL-001")
        assert len(results) == 3

    def test_eviction(self):
        log = ImmutableAuditLog(max_events=5)
        actor = AuditActor.system("test")

        for i in range(8):
            event = AuditEvent(
                event_id=f"AEVT-{i:04d}",
                event_type=AuditEventType.SYSTEM_EVENT,
                entity_type="SYSTEM",
                entity_id="SYS",
                actor=actor,
                action=AuditAction.CREATE,
            )
            log.record(event)

        assert log.size == 5


class TestAuditEngine:
    """Test AuditEngine recording and query."""

    def test_record_event(self):
        engine = AuditEngine()
        actor = AuditActor.human("user-001", "Alice")

        result = engine.record_event(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="DECISION",
            entity_id="DEC-001",
            actor=actor,
            action=AuditAction.CREATE,
            reason="Test",
            correlation_id="CORR-001",
        )
        assert result is not None
        assert engine.events_recorded == 1
        assert engine.chain_length == 1

    def test_record_convenience_methods(self):
        engine = AuditEngine()
        actor = AuditActor.human("user-001")

        r1 = engine.record_decision(
            event_type=AuditEventType.DECISION_APPROVED,
            decision_id="DEC-001",
            actor=actor,
            action=AuditAction.APPROVE,
            reason="Test",
            correlation_id="CORR-002",
        )
        assert r1 is not None

        r2 = engine.record_policy(
            event_type=AuditEventType.POLICY_PUBLISHED,
            policy_id="POL-001",
            actor=actor,
            action=AuditAction.PUBLISH,
            policy_version="v1",
            correlation_id="CORR-002",
        )
        assert r2 is not None

        corr_events = engine.get_events_by_correlation("CORR-002")
        assert len(corr_events) == 2

    def test_integrity_verify(self):
        engine = AuditEngine()
        actor = AuditActor.system("test")

        for i in range(3):
            engine.record_event(
                event_type=AuditEventType.SYSTEM_EVENT,
                entity_type="SYSTEM",
                entity_id=f"SYS-{i}",
                actor=actor,
                action=AuditAction.CREATE,
            )

        result = engine.verify_integrity()
        assert result["valid"] is True

    def test_get_metrics(self):
        engine = AuditEngine()
        actor = AuditActor.system("test")

        engine.record_event(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="DECISION",
            entity_id="DEC-001",
            actor=actor,
            action=AuditAction.CREATE,
        )

        metrics = engine.get_metrics()
        assert metrics["events_recorded"] == 1
        assert metrics["chain_length"] == 1
