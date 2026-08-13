"""Governance audit events (Commit 28 Part 1.5).

- Governance ledger / replay / evidence emit standardised audit events:
  GOVERNANCE_DECISION_CREATED / ALLOWED / DENIED / APPROVAL_REQUIRED,
  GOVERNANCE_DECISION_REPLAYED / REPLAY_MISMATCH, EVIDENCE_CREATED,
  GOVERNANCE_CHAIN_VALIDATED / CHAIN_INVALID.
- GovernanceAuditStore is append-only with decision / type / principal
  queries.
"""

from datetime import datetime, timezone

from services.governance.audit import (
    GovernanceAuditEvent,
    GovernanceAuditEventType,
    GovernanceAuditStore,
    decision_to_audit_event,
)
from services.governance.authority import Authority, AuthoritySource
from services.governance.decision import (
    DecisionEffect,
    GovernanceDecision,
)
from services.governance.decision_ledger import DecisionLedger
from services.governance.decision_replay import DecisionReplayer
from services.governance.evidence import build_evidence
from services.governance.policy import Policy

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_decision(**overrides):
    base = dict(
        decision_id="DEC-001",
        request_id="REQ-001",
        principal_id="ops-001",
        resource="trading",
        action="resume",
        effect=DecisionEffect.ALLOW,
        reason="allowed",
        policy_id="POLICY-RESUME",
        reason_code="GOV_ALLOWED",
        decided_at=NOW,
        sequence=1,
    )
    base.update(overrides)
    return GovernanceDecision(**base)


class TestEventTypes:

    def test_all_part_15_event_types_exist(self):
        expected = {
            "GOVERNANCE_DECISION_CREATED",
            "GOVERNANCE_DECISION_ALLOWED",
            "GOVERNANCE_DECISION_DENIED",
            "GOVERNANCE_APPROVAL_REQUIRED",
            "GOVERNANCE_DECISION_REPLAYED",
            "GOVERNANCE_DECISION_REPLAY_MISMATCH",
            "GOVERNANCE_EVIDENCE_CREATED",
            "GOVERNANCE_CHAIN_VALIDATED",
            "GOVERNANCE_CHAIN_INVALID",
        }
        actual = {member.value for member in GovernanceAuditEventType}
        assert expected == actual


class TestAuditStore:

    def test_store_is_append_only(self):
        store = GovernanceAuditStore()
        event = GovernanceAuditEvent(
            event_id="AUD-001",
            timestamp=NOW,
            principal_id="ops-001",
            resource="trading",
            action="resume",
            effect="ALLOW",
            reason="allowed",
            decision_id="DEC-001",
            event_type=GovernanceAuditEventType.GOVERNANCE_DECISION_CREATED,
        )
        store.record(event)
        store.record(event)
        assert len(store.events) == 2
        assert not hasattr(store, "delete")
        assert not hasattr(store, "update")

    def test_store_query_by_type_and_decision(self):
        store = GovernanceAuditStore()
        store.record(
            GovernanceAuditEvent(
                event_id="AUD-001",
                timestamp=NOW,
                principal_id="ops-001",
                resource="trading",
                action="resume",
                effect="ALLOW",
                reason="allowed",
                decision_id="DEC-001",
                event_type=GovernanceAuditEventType.GOVERNANCE_DECISION_ALLOWED,
            )
        )
        store.record(
            GovernanceAuditEvent(
                event_id="AUD-002",
                timestamp=NOW,
                principal_id="ops-001",
                resource="trading",
                action="resume",
                effect="ALLOW",
                reason="allowed",
                decision_id="DEC-001",
                event_type=GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAYED,
            )
        )
        assert len(store.for_decision("DEC-001")) == 2
        assert len(store.for_decision("DEC-999")) == 0
        assert len(store.for_type(GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAYED)) == 1
        assert len(store.for_principal("ops-001")) == 2


class TestLedgerAudit:

    def test_ledger_emits_created_and_allowed(self):
        store = GovernanceAuditStore()
        ledger = DecisionLedger(auditor=store)
        ledger.append(make_decision())
        types = {event.event_type for event in store.events}
        assert GovernanceAuditEventType.GOVERNANCE_DECISION_CREATED in types
        assert GovernanceAuditEventType.GOVERNANCE_DECISION_ALLOWED in types

    def test_ledger_emits_denied_for_deny(self):
        store = GovernanceAuditStore()
        ledger = DecisionLedger(auditor=store)
        ledger.append(
            make_decision(
                effect=DecisionEffect.DENY,
                reason_code="GOV_DENIED",
            )
        )
        types = {event.event_type for event in store.events}
        assert GovernanceAuditEventType.GOVERNANCE_DECISION_DENIED in types

    def test_ledger_emits_approval_required(self):
        store = GovernanceAuditStore()
        ledger = DecisionLedger(auditor=store)
        ledger.append(
            make_decision(
                effect=DecisionEffect.REQUIRE_APPROVAL,
                reason_code="GOV_APPROVAL_REQUIRED",
            )
        )
        types = {event.event_type for event in store.events}
        assert GovernanceAuditEventType.GOVERNANCE_APPROVAL_REQUIRED in types

    def test_idempotent_append_does_not_duplicate_audit(self):
        store = GovernanceAuditStore()
        ledger = DecisionLedger(auditor=store)
        decision = make_decision()
        ledger.append(decision)
        ledger.append(decision)
        assert len(store.events) == 2


class TestReplayAudit:

    def test_matched_replay_emits_replayed(self):
        store = GovernanceAuditStore()
        decision = make_decision()
        ledger = DecisionLedger(auditor=store)
        ledger.append(decision)
        replayer = DecisionReplayer(ledger=ledger, auditor=store)

        evidence = build_evidence(decision, policy_version="v3")
        policy = Policy(
            policy_id="POLICY-RESUME",
            name="Resume",
            resource="trading",
            action="resume",
            effect="ALLOW",
            version="v3",
        )
        authority = Authority(
            principal_id="ops-001",
            resource="trading",
            actions=("resume",),
            source=AuthoritySource.ROLE,
        )
        request = type("Request", (), {"resource": "trading", "action": "resume"})()

        result = replayer.replay(request, evidence.evidence, policy, authority)
        assert result.matched
        types = {event.event_type for event in store.events}
        assert GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAYED in types

    def test_mismatch_replay_emits_replay_mismatch(self):
        store = GovernanceAuditStore()
        decision = make_decision()
        ledger = DecisionLedger(auditor=store)
        ledger.append(decision)
        replayer = DecisionReplayer(ledger=ledger, auditor=store)

        evidence = build_evidence(decision, policy_version="v3")
        policy = Policy(
            policy_id="POLICY-RESUME",
            name="Resume",
            resource="trading",
            action="resume",
            effect="ALLOW",
            version="v4",
        )
        authority = Authority(
            principal_id="ops-001",
            resource="trading",
            actions=("resume",),
            source=AuthoritySource.ROLE,
        )
        request = type("Request", (), {"resource": "trading", "action": "resume"})()

        result = replayer.replay(request, evidence.evidence, policy, authority)
        assert not result.matched
        types = {event.event_type for event in store.events}
        assert GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAY_MISMATCH in types


class TestEventConversion:

    def test_decision_to_audit_event(self):
        decision = make_decision()
        event = decision_to_audit_event(
            decision,
            GovernanceAuditEventType.GOVERNANCE_DECISION_CREATED,
        )
        assert event.decision_id == "DEC-001"
        assert event.principal_id == "ops-001"
        assert event.effect == "ALLOW"
        assert event.reason_code == "GOV_ALLOWED"
        assert event.policy_id == "POLICY-RESUME"
        assert event.event_type == GovernanceAuditEventType.GOVERNANCE_DECISION_CREATED
        assert event.timestamp == NOW
