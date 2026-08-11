"""
Test Audit Integrity — end-to-end integrity verification scenarios.

Tests:
  - Hash chain creation and verification
  - Tamper detection across events
  - Snapshot integrity
  - Lineage completeness checking
"""

import pytest

from services.governance.audit_event import AuditEvent
from services.governance.audit_event_type import AuditEventType
from services.governance.audit_actor import AuditActor, ActorType
from services.governance.audit_action import AuditAction
from services.governance.audit_outcome import AuditOutcome
from services.governance.audit_engine import AuditEngine
from services.governance.audit_hash import AuditHash
from services.governance.audit_chain import AuditChain
from services.governance.immutable_audit_log import ImmutableAuditLog
from services.governance.audit_integrity import AuditIntegrityChecker
from services.governance.decision_snapshot import DecisionSnapshot


class TestHashChain:
    """Test complete hash chain scenarios."""

    def test_build_and_verify_chain(self):
        """Build a chain of 10 events and verify integrity."""
        engine = AuditEngine()
        actor = AuditActor.system("test-service", "1.0")

        for i in range(10):
            engine.record_event(
                event_type=AuditEventType.DECISION_CREATED,
                entity_type="DECISION",
                entity_id=f"DEC-{i:03d}",
                actor=actor,
                action=AuditAction.CREATE,
                correlation_id="CHAIN-TEST-001",
            )

        assert engine.chain_length == 10
        result = engine.verify_chain()
        assert result["valid"] is True

    def test_build_multiple_correlations(self):
        """Build chains across multiple correlation IDs."""
        engine = AuditEngine()
        actor = AuditActor.system("test")

        for corr in ["CORR-A", "CORR-B", "CORR-C"]:
            for i in range(5):
                engine.record_event(
                    event_type=AuditEventType.SYSTEM_EVENT,
                    entity_type="SYSTEM",
                    entity_id=f"{corr}-{i}",
                    actor=actor,
                    action=AuditAction.CREATE,
                    correlation_id=corr,
                )

        for corr in ["CORR-A", "CORR-B", "CORR-C"]:
            events = engine.get_events_by_correlation(corr)
            assert len(events) == 5

        result = engine.verify_chain()
        assert result["valid"] is True


class TestTamperDetection:
    """Test tamper detection scenarios."""

    def test_detect_modified_event(self):
        """Detect when an event's content is modified."""
        engine = AuditEngine()
        actor = AuditActor.system("test")

        event = engine.record_event(
            event_type=AuditEventType.AUTHORITY_GRANTED,
            entity_type="AUTHORITY",
            entity_id="AUTH-001",
            actor=actor,
            action=AuditAction.GRANT,
            outcome=AuditOutcome.SUCCESS,
            reason="Valid grant",
            correlation_id="TAMPER-TEST",
        )
        assert event is not None

        # Simulate: someone modifies the reason
        original_reason = event.reason
        # We can't actually modify because it's immutable
        # But we can test hash mismatch via to_dict()
        tampered_data = event.to_dict()
        tampered_data["reason"] = "This has been tampered with!"

        # Hash should NOT match
        expected_hash = AuditHash.compute_event_hash(tampered_data)
        assert expected_hash != event.event_hash

    def test_chain_tamper_detection(self):
        """Detect when a chain link's previous_hash is broken."""
        chain = AuditChain()
        chain.append("sha256:event1", "EVT-1")
        chain.append("sha256:event2", "EVT-2")
        chain.append("sha256:event3", "EVT-3")

        # Tamper with link 1
        chain._links[1].previous_hash = "sha256:WRONG_VALUE"

        result = chain.verify()
        assert result["valid"] is False


class TestSnapshotIntegrity:
    """Test decision snapshot integrity."""

    def test_snapshot_hash_consistency(self):
        """Same data produces same hash."""
        data = {
            "snapshot_id": "SNAP-001",
            "decision_id": "DEC-001",
            "market_snapshot": {"NVDA": 182.40},
            "risk_snapshot": {"VaR": 1.8e6},
            "policy_id": "POL-001",
            "policy_version": "v4",
            "authority_id": "AUTH-001",
            "approval_id": "APR-001",
            "decision_type": "CAPITAL_ALLOCATION",
            "instrument": "NVDA",
            "side": "BUY",
            "quantity": 137100,
            "amount": 25_000_000,
            "timestamp": 1000000.0,
        }

        h1 = AuditHash.compute_snapshot_hash(data)
        h2 = AuditHash.compute_snapshot_hash(dict(data))
        assert h1 == h2

    def test_snapshot_hash_changes_with_data(self):
        """Different data produces different hash."""
        data = {
            "snapshot_id": "SNAP-001",
            "decision_id": "DEC-001",
            "instrument": "NVDA",
            "amount": 25_000_000,
            "timestamp": 1.0,
        }
        h1 = AuditHash.compute_snapshot_hash(data)
        data["amount"] = 26_000_000
        h2 = AuditHash.compute_snapshot_hash(data)
        assert h1 != h2


class TestLineageCompleteness:
    """Test lineage completeness checks."""

    def test_event_correlation_ids(self):
        """Events in same correlation are linked."""
        engine = AuditEngine()
        actor = AuditActor.system("test")

        events = []
        for i, (etype, etype_str, eid) in enumerate([
            (AuditEventType.DECISION_CREATED, "DECISION", "DEC-001"),
            (AuditEventType.POLICY_ACTIVATED, "POLICY", "POL-001"),
            (AuditEventType.AUTHORITY_GRANTED, "AUTHORITY", "AUTH-001"),
            (AuditEventType.APPROVAL_APPROVED, "APPROVAL", "APR-001"),
        ]):
            event = engine.record_event(
                event_type=etype,
                entity_type=etype_str,
                entity_id=eid,
                actor=actor,
                action=AuditAction.CREATE,
                correlation_id="FULL-CHAIN-001",
                causation_id="" if i == 0 else f"CAUSE-{i-1:03d}",
            )
            events.append(event)

        corr_events = engine.get_events_by_correlation("FULL-CHAIN-001")
        assert len(corr_events) == 4
        # All share the same correlation
        for e in corr_events:
            assert e.correlation_id == "FULL-CHAIN-001"
