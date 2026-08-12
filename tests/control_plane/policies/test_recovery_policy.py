"""Unit tests: recovery-progression-policy."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.trading_gate import RiskIntegrity
from services.control_plane.policies.recovery_policy import (
    POLICY_ID,
    build_recovery_policy,
)
from services.control_plane.policy.policy_action import PolicyActionType
from services.control_plane.policy.policy_context import (
    PolicyContext,
    RecoveryState,
)
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine


def _engine() -> PolicyEngine:
    engine = PolicyEngine()
    engine.register_policy(build_recovery_policy())
    return engine


class TestRecoveryPolicy:
    def test_no_recovery_does_not_fire(self):
        evaluation = _engine().evaluate(PolicyContext())
        assert evaluation.decision is PolicyDecision.ALLOW
        assert evaluation.matched_policies == []

    def test_running_restricts(self):
        evaluation = _engine().evaluate(
            PolicyContext(recovery_state=RecoveryState.RUNNING)
        )
        assert evaluation.decision is PolicyDecision.DEGRADE
        assert evaluation.reasons == ["RECOVERY_IN_PROGRESS"]

    def test_failed_blocks_and_escalates(self):
        evaluation = _engine().evaluate(
            PolicyContext(recovery_state=RecoveryState.FAILED)
        )
        assert evaluation.decision is PolicyDecision.BLOCK
        types = {a.action_type for a in evaluation.actions}
        assert PolicyActionType.START_RECOVERY in types
        assert PolicyActionType.ESCALATE_INCIDENT in types

    def test_completed_but_integrity_missing_stays_blocked(self):
        evaluation = _engine().evaluate(
            PolicyContext(
                recovery_state=RecoveryState.COMPLETED,
                position_integrity=RiskIntegrity.UNTRUSTED,
            )
        )
        assert "recovery-verified-ramp" not in evaluation.matched_rules

    def test_completed_and_verified_returns_recover(self):
        evaluation = _engine().evaluate(
            PolicyContext(
                recovery_state=RecoveryState.COMPLETED,
                position_integrity=RiskIntegrity.TRUSTED,
                ledger_integrity=RiskIntegrity.TRUSTED,
                risk_health=ComponentState.HEALTHY,
            )
        )
        assert evaluation.decision is PolicyDecision.RECOVER
        assert "recovery-verified-ramp" in evaluation.matched_rules
        assert evaluation.policy_versions[POLICY_ID] == "1.0.0"
