"""Decision immutability (Commit 28 Part 1.5).

- The ledger is append-only: entries can never be updated or deleted.
- Entries are frozen dataclasses: in-place mutation is impossible.
- Tampering with any entry breaks the hash chain (verified by the
  DecisionChainValidator).
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from services.governance.decision import DecisionEffect, GovernanceDecision
from services.governance.decision_ledger import DecisionLedger
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


class TestAppendOnly:

    def test_entries_cannot_be_mutated_in_place(self):
        ledger = build_chain()
        entry = ledger.entries[0]
        with pytest.raises(FrozenInstanceError):
            entry.reason_code = "GOV_ALLOWED"

    def test_ledger_exposes_no_mutation_beyond_append(self):
        ledger = DecisionLedger()
        ledger.append(make_decision())
        # Append-only: the only write API is append().
        mutators = [name for name in dir(ledger) if name.startswith(("update", "delete", "remove", "set", "clear"))]
        assert mutators == []

    def test_entries_tuple_is_not_the_live_list(self):
        ledger = build_chain()
        snapshot = ledger.entries
        ledger.append(
            make_decision(
                decision_id="DEC-004",
                request_id="REQ-004",
                sequence=4,
            )
        )
        assert len(snapshot) == 3
        assert len(ledger.entries) == 4


class TestTamperDetection:

    def test_tampering_first_entry_is_detected(self):
        """Spec §33 — flipping the first decision breaks the chain."""
        ledger = build_chain()
        validator = DecisionChainValidator()
        assert validator.validate(ledger.entries)

        tampered = replace(ledger.entries[0], reason_code="GOV_DENIED")
        entries = [tampered, *ledger.entries[1:]]
        assert not validator.validate(entries)

    def test_tampering_middle_entry_is_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()

        tampered = replace(ledger.entries[1], effect="ALLOW")
        entries = [ledger.entries[0], tampered, ledger.entries[2]]
        assert not validator.validate(entries)

    def test_tampering_decision_id_is_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()

        tampered = replace(ledger.entries[2], decision_id="DEC-999")
        entries = [ledger.entries[0], ledger.entries[1], tampered]
        assert not validator.validate(entries)

    def test_tampering_timestamp_is_detected(self):
        ledger = build_chain()
        validator = DecisionChainValidator()

        tampered = replace(
            ledger.entries[0],
            timestamp=datetime(2026, 8, 13, 11, 0, 0, tzinfo=timezone.utc),
        )
        entries = [tampered, *ledger.entries[1:]]
        assert not validator.validate(entries)

    def test_untouched_chain_remains_valid(self):
        ledger = build_chain()
        validator = DecisionChainValidator()
        assert validator.validate(ledger.entries)
        assert validator.validate(ledger.entries[:2])
