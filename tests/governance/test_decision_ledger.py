"""Decision ledger (Commit 28 Part 1.5).

- Append-only ledger with strict sequence (1, 2, 3, ...).
- Hash chain: every entry links previous_hash -> entry_hash.
- Idempotency: same request_id + same fingerprint returns the existing entry.
- Request mutation: same request_id + different fingerprint is rejected with
  REQUEST_ID_REUSE_CONFLICT.
"""

from datetime import datetime, timezone

import pytest

from services.governance.decision import (
    DecisionEffect,
    GovernanceDecision,
)
from services.governance.decision_ledger import (
    DecisionLedger,
    DecisionLedgerEngine,
    GovernanceRequest,
    RequestReuseConflictError,
    calculate_hash,
    request_fingerprint,
)

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_decision(**overrides):
    base = dict(
        decision_id="DEC-001",
        request_id="REQ-001",
        principal_id="ops-001",
        resource="trading",
        action="resume",
        effect=DecisionEffect.ALLOW,
        reason="allowed by POLICY-RESUME",
        policy_id="POLICY-RESUME",
        reason_code="GOV_ALLOWED",
        decided_at=NOW,
        sequence=1,
    )
    base.update(overrides)
    return GovernanceDecision(**base)


class TestAppendOnly:

    def test_first_entry_is_genesis(self):
        ledger = DecisionLedger()
        entry = ledger.append(make_decision())
        assert entry.sequence == 1
        assert entry.previous_hash is None
        assert ledger.last_hash == entry.entry_hash

    def test_sequence_increases_strictly(self):
        ledger = DecisionLedger()
        first = ledger.append(make_decision(decision_id="DEC-001", request_id="REQ-001"))
        second = ledger.append(
            make_decision(
                decision_id="DEC-002",
                request_id="REQ-002",
                effect=DecisionEffect.DENY,
                reason_code="GOV_DENIED",
                sequence=2,
            )
        )
        third = ledger.append(
            make_decision(
                decision_id="DEC-003",
                request_id="REQ-003",
                effect=DecisionEffect.REQUIRE_APPROVAL,
                reason_code="GOV_APPROVAL_REQUIRED",
                sequence=3,
            )
        )
        assert [e.sequence for e in ledger.entries] == [1, 2, 3]
        assert second.previous_hash == first.entry_hash
        assert third.previous_hash == second.entry_hash

    def test_entries_are_a_tuple_snapshot(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        ledger.append(
            make_decision(
                decision_id="DEC-002",
                request_id="REQ-002",
                sequence=2,
            )
        )
        snapshot = ledger.entries
        assert isinstance(snapshot, tuple)
        assert len(snapshot) == 2

    def test_append_requires_request_id(self):
        ledger = DecisionLedger()
        with pytest.raises(ValueError):
            ledger.append(make_decision(request_id=None))

    def test_no_update_no_delete(self):
        """Append-only: the ledger exposes no update / delete API."""
        ledger = DecisionLedger()
        ledger.append(make_decision())
        assert not hasattr(ledger, "update")
        assert not hasattr(ledger, "delete")
        assert not hasattr(ledger, "remove")


class TestLookup:

    def test_get_by_request(self):
        ledger = DecisionLedger()
        decision = make_decision()
        ledger.append(decision)
        assert ledger.get_by_request("REQ-001") == decision
        assert ledger.get_by_request("REQ-999") is None

    def test_get_by_decision(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        assert ledger.get_by_decision("DEC-001") is not None
        assert ledger.get_by_decision("DEC-999") is None

    def test_get_entry_by_request(self):
        ledger = DecisionLedger()
        entry = ledger.append(make_decision())
        assert ledger.get_entry_by_request("REQ-001") == entry


class TestIdempotency:

    def test_same_request_returns_existing_entry(self):
        ledger = DecisionLedger()
        decision = make_decision()
        first = ledger.append(decision)
        second = ledger.append(decision)
        assert first == second
        assert ledger.size == 1
        assert ledger.get_by_request("REQ-001").decision_id == "DEC-001"

    def test_same_fingerprint_returns_existing_entry(self):
        ledger = DecisionLedger()
        decision = make_decision()
        ledger.append(decision)
        clone = make_decision(decision_id="DEC-001")  # identical request
        entry = ledger.append(clone)
        assert entry.sequence == 1
        assert ledger.size == 1

    def test_request_fingerprint_is_stable(self):
        fp1 = request_fingerprint("ops-001", "trading", "resume")
        fp2 = request_fingerprint("ops-001", "trading", "resume")
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_fingerprint_differs_on_any_field(self):
        base = request_fingerprint("ops-001", "trading", "resume")
        assert request_fingerprint("ops-002", "trading", "resume") != base
        assert request_fingerprint("ops-001", "trading", "kill") != base
        assert request_fingerprint("ops-001", "trading", "resume", context_hash="c1") != base


class TestRequestMutation:

    def test_reuse_conflict_raises(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        mutated = make_decision(
            decision_id="DEC-002",
            principal_id="other-001",
            resource="trading",
            action="kill",
            reason_code="GOV_DENIED",
        )
        with pytest.raises(RequestReuseConflictError) as exc:
            ledger.append(mutated)
        assert exc.value.reason_code == "REQUEST_ID_REUSE_CONFLICT"

    def test_reuse_conflict_reason_code(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        mutated = make_decision(
            decision_id="DEC-002",
            principal_id="other-001",
        )
        with pytest.raises(RequestReuseConflictError):
            ledger.append(mutated)


class TestHashComputation:

    def test_entry_hash_matches_calculate_hash(self):
        ledger = DecisionLedger()
        decision = make_decision()
        entry = ledger.append(decision)
        expected = calculate_hash(
            sequence=1,
            decision_id="DEC-001",
            request_id="REQ-001",
            effect="ALLOW",
            reason_code="GOV_ALLOWED",
            timestamp=NOW,
            previous_hash=None,
        )
        assert entry.entry_hash == expected

    def test_last_hash_tracks_latest_entry(self):
        ledger = DecisionLedger()
        first = ledger.append(make_decision())
        second = ledger.append(
            make_decision(
                decision_id="DEC-002",
                request_id="REQ-002",
                sequence=2,
            )
        )
        assert ledger.last_hash == second.entry_hash
        assert first.entry_hash != second.entry_hash


class TestLedgerEngine:

    def test_evaluate_records_decision(self):
        engine = DecisionLedgerEngine()
        request = GovernanceRequest(
            request_id="REQ-001",
            principal_id="ops-001",
            resource="trading",
            action="resume",
        )
        decision = engine.evaluate(request)
        assert decision.request_id == "REQ-001"
        assert engine.ledger.size == 1
        assert engine.ledger.get_by_request("REQ-001") == decision

    def test_request_is_idempotent(self):
        """Spec §36 — same request produces the same decision."""
        engine = DecisionLedgerEngine()
        request = GovernanceRequest(
            request_id="REQ-001",
            principal_id="ops-001",
            resource="trading",
            action="resume",
        )
        first = engine.evaluate(request)
        second = engine.evaluate(request)
        assert first.decision_id == second.decision_id
        assert engine.ledger.size == 1

    def test_request_reuse_conflict(self):
        """Spec §37 — same request_id with different context is DENY."""
        engine = DecisionLedgerEngine()
        request_a = GovernanceRequest(
            request_id="REQ-001",
            principal_id="ops-001",
            resource="trading",
            action="resume",
            context_hash="ctx-a",
        )
        engine.evaluate(request_a)
        request_b = GovernanceRequest(
            request_id="REQ-001",
            principal_id="ops-001",
            resource="trading",
            action="kill",
            context_hash="ctx-b",
        )
        result = engine.evaluate(request_b)
        assert result.effect == DecisionEffect.DENY
        assert result.reason_code == "REQUEST_ID_REUSE_CONFLICT"
