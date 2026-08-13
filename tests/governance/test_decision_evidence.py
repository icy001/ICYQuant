"""Decision evidence (Commit 28 Part 1.5).

- Evidence captures the exact policy version, authority snapshot, approval
  state, quorum outcome and context hash a decision was based on.
- Evidence is hashed: any modification of the evidence is detected.
- Policy updates (v3 -> v4) never rewrite history: DEC-001 stays on v3.
"""

from dataclasses import replace
from datetime import datetime, timezone

from services.governance.decision import (
    DecisionEffect,
    GovernanceDecision,
)
from services.governance.evidence import (
    EvidenceEnvelope,
    build_evidence,
    verify_envelope,
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
        reason="allowed",
        policy_id="POLICY-RESUME",
        approval_id="APR-001",
        reason_code="GOV_ALLOWED",
        decided_at=NOW,
        sequence=1,
        context_hash="ctx-1",
    )
    base.update(overrides)
    return GovernanceDecision(**base)


class TestEvidenceBuild:

    def test_evidence_captures_decision_inputs(self):
        decision = make_decision()
        envelope = build_evidence(
            decision,
            policy_version="v3",
            authority_snapshot=("CONTROL_OPERATOR", "INCIDENT_COMMANDER"),
            approval_state="APPROVED",
            quorum_met=True,
        )
        assert isinstance(envelope, EvidenceEnvelope)
        evidence = envelope.evidence
        assert evidence.decision_id == "DEC-001"
        assert evidence.policy_id == "POLICY-RESUME"
        assert evidence.policy_version == "v3"
        assert evidence.principal_id == "ops-001"
        assert evidence.authority_snapshot == ("CONTROL_OPERATOR", "INCIDENT_COMMANDER")
        assert evidence.approval_id == "APR-001"
        assert evidence.approval_state == "APPROVED"
        assert evidence.quorum_met is True
        assert evidence.context_hash == "ctx-1"

    def test_evidence_hash_matches_envelope(self):
        decision = make_decision()
        envelope = build_evidence(decision, policy_version="v3")
        assert envelope.evidence_hash is not None
        assert verify_envelope(envelope)

    def test_tampered_evidence_is_detected(self):
        decision = make_decision()
        envelope = build_evidence(decision, policy_version="v3")
        tampered = replace(envelope.evidence, policy_version="v4")
        forged = EvidenceEnvelope(
            evidence=tampered,
            evidence_hash=envelope.evidence_hash,
        )
        assert not verify_envelope(forged)

    def test_modified_authority_snapshot_is_detected(self):
        decision = make_decision()
        envelope = build_evidence(
            decision,
            policy_version="v3",
            authority_snapshot=("CONTROL_OPERATOR",),
        )
        tampered = replace(
            envelope.evidence,
            authority_snapshot=("CONTROL_OPERATOR", "RISK_OWNER"),
        )
        forged = EvidenceEnvelope(evidence=tampered, evidence_hash=envelope.evidence_hash)
        assert not verify_envelope(forged)


class TestHistoricalVersion:

    def test_policy_version_is_preserved(self):
        """Spec §15/§16 — DEC-001 remains bound to v3 after v4 ships."""
        decision = make_decision()
        envelope = build_evidence(decision, policy_version="v3")
        # Today the policy is v4, but the evidence still says v3.
        assert envelope.evidence.policy_version == "v3"

    def test_evidence_carries_context_hash(self):
        decision = make_decision(context_hash="a81c...93fe")
        envelope = build_evidence(decision, policy_version="v3")
        assert envelope.evidence.context_hash == "a81c...93fe"

    def test_evidence_default_context_hash(self):
        decision = make_decision(context_hash=None)
        envelope = build_evidence(decision, policy_version="v3")
        assert envelope.evidence.context_hash == ""


class TestEvidenceIntegrity:

    def test_rebuild_envelope_after_legitimate_change(self):
        """A legitimate new version must produce a new (valid) hash."""
        decision = make_decision()
        v3 = build_evidence(decision, policy_version="v3")
        v4 = build_evidence(decision, policy_version="v4")
        assert v3.evidence_hash != v4.evidence_hash
        assert verify_envelope(v3)
        assert verify_envelope(v4)
