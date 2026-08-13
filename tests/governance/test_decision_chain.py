"""Decision hash chain (Commit 28 Part 1.5).

    D001 -> hash -> D002 -> hash -> D003
    任何一条被修改都会破坏整条链（Spec §8 / §13 / §32 / §33）。
"""

from dataclasses import replace
from datetime import datetime, timezone

from services.governance.decision import DecisionEffect, GovernanceDecision
from services.governance.decision_ledger import (
    DecisionLedger,
    DecisionLedgerEngine,
    GovernanceRequest,
)
from services.governance.decision_replay import DecisionChainValidator

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


def build_chain():
    ledger = DecisionLedger()
    ledger.append(make_decision())
    ledger.append(
        make_decision(
            decision_id="DEC-002",
            request_id="REQ-002",
            effect=DecisionEffect.DENY,
            reason_code="GOV_DENIED",
            sequence=2,
        )
    )
    ledger.append(
        make_decision(
            decision_id="DEC-003",
            request_id="REQ-003",
            effect=DecisionEffect.REQUIRE_APPROVAL,
            reason_code="GOV_APPROVAL_REQUIRED",
            sequence=3,
        )
    )
    return ledger


class TestChainValidation:

    def test_decision_chain(self):
        """Spec §32 — a well-formed chain validates."""
        ledger = build_chain()
        assert DecisionChainValidator().validate(ledger.entries)

    def test_empty_chain_is_valid(self):
        assert DecisionChainValidator().validate(())

    def test_single_entry_chain_is_valid(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        assert DecisionChainValidator().validate(ledger.entries)

    def test_chain_links_are_contiguous(self):
        ledger = build_chain()
        entries = ledger.entries
        for previous, current in zip(entries, entries[1:]):
            assert current.previous_hash == previous.entry_hash

    def test_first_entry_has_no_predecessor(self):
        ledger = build_chain()
        assert ledger.entries[0].previous_hash is None

    def test_prefix_chain_is_valid(self):
        ledger = build_chain()
        validator = DecisionChainValidator()
        assert validator.validate(ledger.entries[:2])


class TestTamperDetection:

    def test_deny_flipped_to_allow_is_detected(self):
        """Spec §13 — D002 DENY -> ALLOW breaks the chain."""
        ledger = build_chain()
        validator = DecisionChainValidator()
        assert validator.validate(ledger.entries)

        tampered = replace(ledger.entries[1], effect="ALLOW")
        entries = [ledger.entries[0], tampered, ledger.entries[2]]
        assert not validator.validate(entries)

    def test_reason_code_flip_is_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()

        tampered = replace(ledger.entries[2], reason_code="GOV_ALLOWED")
        entries = [ledger.entries[0], ledger.entries[1], tampered]
        assert not validator.validate(entries)

    def test_broken_link_is_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()

        tampered = replace(ledger.entries[1], previous_hash="deadbeef")
        entries = [ledger.entries[0], tampered, ledger.entries[2]]
        assert not validator.validate(entries)

    def test_swapped_entries_are_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()
        swapped = [ledger.entries[1], ledger.entries[0], ledger.entries[2]]
        assert not validator.validate(swapped)


class TestEngineChain:

    def test_engine_produces_valid_chain(self):
        engine = DecisionLedgerEngine()
        for index in range(3):
            engine.evaluate(
                GovernanceRequest(
                    request_id=f"REQ-{index + 1:03d}",
                    principal_id="ops-001",
                    resource="trading",
                    action="resume",
                )
            )
        assert DecisionChainValidator().validate(engine.ledger.entries)
        assert [entry.sequence for entry in engine.ledger.entries] == [1, 2, 3]

    def test_engine_idempotency_keeps_chain_intact(self):
        engine = DecisionLedgerEngine()
        request = GovernanceRequest(
            request_id="REQ-001",
            principal_id="ops-001",
            resource="trading",
            action="resume",
        )
        engine.evaluate(request)
        engine.evaluate(request)
        assert engine.ledger.size == 1
        assert DecisionChainValidator().validate(engine.ledger.entries)
