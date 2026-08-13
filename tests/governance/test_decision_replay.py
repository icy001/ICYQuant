"""Decision replay (Commit 28 Part 1.5).

- Replay recomputes *why* a historical decision was made — it never
  executes the control (no pause / resume / kill side effects).
- Historical replay must use the policy version captured in the evidence.
- Mismatches are explained with concrete codes:
  POLICY_VERSION_MISMATCH / AUTHORITY_STATE_CHANGED / APPROVAL_EXPIRED /
  QUORUM_NOT_MET.
"""

from datetime import datetime, timezone

from services.governance.authority import Authority, AuthoritySource
from services.governance.decision import (
    DecisionEffect,
    GovernanceDecision,
)
from services.governance.decision_ledger import (
    DecisionLedger,
    GovernanceRequest,
)
from services.governance.decision_replay import DecisionReplayer, ReplayResult
from services.governance.evidence import build_evidence
from services.governance.policy import Policy

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)

REQUEST = GovernanceRequest(
    request_id="REQ-001",
    principal_id="ops-001",
    role_ids=("CONTROL_OPERATOR",),
    resource="trading",
    action="resume",
    environment="production",
)

AUTHORITY = Authority(
    principal_id="ops-001",
    resource="trading",
    actions=("resume",),
    source=AuthoritySource.ROLE,
)


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
        authority_source="ROLE",
        reason_code="GOV_ALLOWED",
        decided_at=NOW,
        sequence=1,
        context_hash="ctx-1",
    )
    base.update(overrides)
    return GovernanceDecision(**base)


def make_policy(version="v3"):
    return Policy(
        policy_id="POLICY-RESUME",
        name="Production Trading Resume",
        resource="trading",
        action="resume",
        effect="ALLOW",
        priority=50,
        version=version,
    )


def make_replayer(decision=None, auditor=None):
    ledger = DecisionLedger(auditor=auditor)
    if decision is not None:
        ledger.append(decision)
    return DecisionReplayer(ledger=ledger)


class TestMatchedReplay:

    def test_decision_replay(self):
        """Spec §34 — replay with the original policy version matches."""
        decision = make_decision()
        evidence = build_evidence(
            decision,
            policy_version="v3",
            authority_snapshot=("CONTROL_OPERATOR",),
            context_hash="ctx-1",
        )
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v3"), AUTHORITY)
        assert isinstance(result, ReplayResult)
        assert result.matched
        assert result.original_effect == DecisionEffect.ALLOW
        assert result.replayed_effect == DecisionEffect.ALLOW
        assert result.mismatches == ()

    def test_original_decision_id_is_reported(self):
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v3"), AUTHORITY)
        assert result.original_decision_id == "DEC-001"


class TestMismatchReplay:

    def test_replay_mismatch_policy_version(self):
        """Spec §35 — a newer policy version produces a mismatch."""
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v4"), AUTHORITY)
        assert not result.matched
        assert "POLICY_VERSION_MISMATCH" in result.mismatches

    def test_replay_mismatch_wrong_policy_id(self):
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        wrong_policy = Policy(
            policy_id="POLICY-OTHER",
            name="Other",
            resource="trading",
            action="resume",
            effect="ALLOW",
            version="v3",
        )
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, wrong_policy, AUTHORITY)
        assert not result.matched
        assert "POLICY_VERSION_MISMATCH" in result.mismatches

    def test_replay_mismatch_authority_changed(self):
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        revoked = Authority(
            principal_id="ops-001",
            resource="trading",
            actions=("pause",),
            source=AuthoritySource.ROLE,
        )
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v3"), revoked)
        assert not result.matched
        assert "AUTHORITY_STATE_CHANGED" in result.mismatches

    def test_replay_mismatch_approval_expired(self):
        decision = make_decision(approval_id="APR-001")
        evidence = build_evidence(
            decision,
            policy_version="v3",
            approval_state="PENDING",
        )
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v3"), AUTHORITY)
        assert not result.matched
        assert "APPROVAL_EXPIRED" in result.mismatches

    def test_replay_mismatch_quorum_not_met(self):
        decision = make_decision(approval_id="APR-001")
        evidence = build_evidence(
            decision,
            policy_version="v3",
            approval_state="APPROVED",
            quorum_met=False,
        )
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, make_policy("v3"), AUTHORITY)
        assert not result.matched
        assert "QUORUM_NOT_MET" in result.mismatches


class TestReplaySafety:

    def test_replay_only_recomputes_never_executes(self):
        """Spec §20 — replay must never trigger control execution."""
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        replayer = make_replayer(decision)
        result = replayer.replay(REQUEST, evidence.evidence, make_policy("v3"), AUTHORITY)
        # The only observable output is the recomputed decision.
        assert result.replayed_effect in (
            DecisionEffect.ALLOW,
            DecisionEffect.DENY,
            DecisionEffect.REQUIRE_APPROVAL,
        )
        assert replayer.ledger.size == 1  # replay appends nothing

    def test_replay_without_ledger_still_works(self):
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        result = DecisionReplayer().replay(
            REQUEST,
            evidence.evidence,
            make_policy("v3"),
            AUTHORITY,
            original_decision=decision,
        )
        assert result.matched

    def test_historical_replay_uses_evidence_version(self):
        """Spec §23 — replay uses v3 (evidence), not the current v5."""
        decision = make_decision()
        evidence = build_evidence(decision, policy_version="v3")
        current = make_policy("v5")
        result = make_replayer(decision).replay(REQUEST, evidence.evidence, current, AUTHORITY)
        assert not result.matched
        assert "POLICY_VERSION_MISMATCH" in result.mismatches
