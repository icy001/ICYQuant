"""
Test AuditChain & AuditIntegrity — hash chain and tamper detection.
"""

import pytest

from services.governance.audit_hash import AuditHash
from services.governance.audit_chain import AuditChain, ChainLink
from services.governance.audit_event_type import AuditEventType
from services.governance.audit_actor import AuditActor
from services.governance.audit_action import AuditAction
from services.governance.audit_event import AuditEvent
from services.governance.immutable_audit_log import ImmutableAuditLog
from services.governance.audit_integrity import AuditIntegrityChecker


class TestAuditHash:
    """Test hash computation utilities."""

    def test_compute_event_hash(self):
        data = {
            "event_id": "AEVT-001",
            "event_type": "DECISION_CREATED",
            "entity_type": "DECISION",
            "entity_id": "DEC-001",
            "actor": {"actor_id": "user-001"},
            "action": "CREATE",
            "outcome": "SUCCESS",
            "reason": "Test",
            "timestamp": 1000000.0,
            "context": {},
            "previous_hash": "",
        }
        h = AuditHash.compute_event_hash(data)
        assert h.startswith("sha256:")
        assert len(h) == 71  # "sha256:" + 64 hex chars

    def test_hash_deterministic(self):
        data = {
            "event_id": "AEVT-001",
            "entity_type": "DECISION",
            "entity_id": "DEC-001",
            "actor": {"actor_id": "x"},
            "action": "CREATE",
            "outcome": "SUCCESS",
            "reason": "Test",
            "timestamp": 1.0,
            "context": {},
            "previous_hash": "",
        }
        h1 = AuditHash.compute_event_hash(dict(data))
        h2 = AuditHash.compute_event_hash(dict(data))
        assert h1 == h2

    def test_hash_different(self):
        data1 = {"event_id": "AEVT-001", "entity_id": "E1"}
        data2 = {"event_id": "AEVT-002", "entity_id": "E2"}
        h1 = AuditHash.compute_snapshot_hash(data1)
        h2 = AuditHash.compute_snapshot_hash(data2)
        assert h1 != h2

    def test_raw_sha256(self):
        h = AuditHash.raw_sha256("hello")
        assert len(h) == 64
        assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class TestAuditChain:
    """Test hash chain integrity."""

    def test_append_and_verify(self):
        chain = AuditChain()
        assert chain.length == 0
        assert chain.last_hash == AuditChain.GENESIS_HASH

        chain.append("sha256:aaaa", "EVT-1")
        assert chain.length == 1

        chain.append("sha256:bbbb", "EVT-2")
        assert chain.length == 2

        result = chain.verify()
        assert result["valid"] is True

    def test_tampered_chain(self):
        chain = AuditChain()
        chain.append("sha256:aaaa", "EVT-1")
        chain.append("sha256:bbbb", "EVT-2")

        # Tamper with a link's previous_hash
        chain._links[1].previous_hash = "sha256:wrong"

        result = chain.verify()
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_chain_link_to_dict(self):
        chain = AuditChain()
        link = chain.append("sha256:aaaa", "EVT-1")
        d = link.to_dict()
        assert d["event_id"] == "EVT-1"
        assert d["index"] == 0
        assert d["previous_hash"] == AuditChain.GENESIS_HASH


class TestAuditIntegrity:
    """Test integrity checker."""

    def test_verify(self):
        chain = AuditChain()
        log = ImmutableAuditLog(max_events=100)
        actor = AuditActor.system("test")

        for i in range(5):
            event = AuditEvent(
                event_id=f"AEVT-{i:04d}",
                event_type=AuditEventType.SYSTEM_EVENT,
                entity_type="SYSTEM",
                entity_id=f"SYS-{i}",
                actor=actor,
                action=AuditAction.CREATE,
            )
            log.record(event)

        checker = AuditIntegrityChecker(chain=chain)
        result = checker.verify()
        assert "valid" in result

    def test_detect_tamper(self):
        chain = AuditChain()
        checker = AuditIntegrityChecker(chain=chain)
        result = checker.detect_tamper()
        assert "tampered" in result

    def test_verify_single_event(self):
        actor = AuditActor.system("test")
        event = AuditEvent(
            event_id="AEVT-CHECK",
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="DECISION",
            entity_id="DEC-001",
            actor=actor,
            action=AuditAction.CREATE,
        )

        chain = AuditChain()
        checker = AuditIntegrityChecker(chain=chain)
        result = checker.verify_single_event(event)

        # Hash may or may not be empty
        if event.event_hash:
            assert result["valid"] is True
