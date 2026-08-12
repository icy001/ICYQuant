"""Unit tests: recovery trigger policies (Policy Engine integration)."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.trading_gate import RiskIntegrity
from services.control_plane.policy.policy_action import PolicyActionType
from services.control_plane.policy.policy_context import PolicyContext
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.recovery_policies import (
    EVENT_RECOVERY_POLICY_ID,
    GLOBAL_RECOVERY_POLICY_ID,
    LEDGER_RECOVERY_POLICY_ID,
    POSITION_RECOVERY_POLICY_ID,
    build_event_recovery_policy,
    build_global_recovery_policy,
    build_ledger_recovery_policy,
    build_position_recovery_policy,
    build_recovery_policies,
    register_recovery_policies,
)
def _actions(decision_eval) -> dict:
    return {
        (a.action_type, a.target): a
        for a in decision_eval.actions
    }


class TestPositionRecoveryPolicy:
    def test_policy_identity(self):
        policy = build_position_recovery_policy()
        assert policy.policy_id == POSITION_RECOVERY_POLICY_ID
        assert policy.policy_version == "1.0.0"

    def test_untrusted_position_triggers_recovery(self):
        policy = build_position_recovery_policy()
        result = policy.evaluate(
            PolicyContext(position_integrity=RiskIntegrity.UNTRUSTED)
        )
        assert result.matched
        assert result.decision is PolicyDecision.BLOCK
        actions = _actions(result)
        assert (PolicyActionType.START_RECOVERY, "POSITION") in actions

    def test_unhealthy_position_triggers_recovery(self):
        policy = build_position_recovery_policy()
        result = policy.evaluate(
            PolicyContext(position_health=ComponentState.UNHEALTHY)
        )
        assert result.matched
        assert result.decision is PolicyDecision.BLOCK

    def test_healthy_position_no_match(self):
        policy = build_position_recovery_policy()
        result = policy.evaluate(
            PolicyContext(position_integrity=RiskIntegrity.TRUSTED)
        )
        assert not result.matched


class TestLedgerRecoveryPolicy:
    def test_untrusted_ledger_triggers_recovery(self):
        policy = build_ledger_recovery_policy()
        result = policy.evaluate(
            PolicyContext(ledger_integrity=RiskIntegrity.UNTRUSTED)
        )
        assert result.matched
        assert result.decision is PolicyDecision.BLOCK
        actions = _actions(result)
        assert (PolicyActionType.START_RECOVERY, "LEDGER") in actions

    def test_trusted_ledger_no_match(self):
        policy = build_ledger_recovery_policy()
        result = policy.evaluate(PolicyContext())
        assert not result.matched


class TestEventRecoveryPolicy:
    def test_unhealthy_event_bus_triggers_recovery(self):
        policy = build_event_recovery_policy()
        result = policy.evaluate(
            PolicyContext(event_bus_health=ComponentState.UNHEALTHY)
        )
        assert result.matched
        assert result.decision is PolicyDecision.BLOCK
        actions = _actions(result)
        assert (PolicyActionType.START_RECOVERY, "EVENTS") in actions

    def test_healthy_event_bus_no_match(self):
        policy = build_event_recovery_policy()
        result = policy.evaluate(PolicyContext())
        assert not result.matched


class TestGlobalRecoveryPolicy:
    def test_policy_identity(self):
        policy = build_global_recovery_policy()
        assert policy.policy_id == GLOBAL_RECOVERY_POLICY_ID

    def test_risk_failure_triggers_global_recovery(self):
        policy = build_global_recovery_policy()
        result = policy.evaluate(
            PolicyContext(
                risk_integrity=RiskIntegrity.UNTRUSTED,
                risk_health=ComponentState.UNHEALTHY,
            )
        )
        assert result.matched
        assert result.decision is PolicyDecision.HALT
        actions = _actions(result)
        assert (PolicyActionType.ACTIVATE_KILL_SWITCH, "GLOBAL") in actions
        assert (PolicyActionType.START_RECOVERY, "GLOBAL") in actions

    def test_running_recovery_denies_new_orders(self):
        policy = build_global_recovery_policy()
        result = policy.evaluate(
            PolicyContext(recovery_state="RUNNING")
        )
        assert result.matched
        assert result.decision is PolicyDecision.DEGRADE

    def test_completed_recovery_allows_when_healthy(self):
        policy = build_global_recovery_policy()
        result = policy.evaluate(
            PolicyContext(
                recovery_state="COMPLETED",
                risk_health=ComponentState.HEALTHY,
                position_integrity=RiskIntegrity.TRUSTED,
                ledger_integrity=RiskIntegrity.TRUSTED,
            )
        )
        assert result.matched
        assert result.decision is PolicyDecision.ALLOW

    def test_completed_recovery_not_allowed_if_risk_unhealthy(self):
        policy = build_global_recovery_policy()
        result = policy.evaluate(
            PolicyContext(
                recovery_state="COMPLETED",
                risk_health=ComponentState.UNHEALTHY,
            )
        )
        # the allow rule does not fire; the risk rule takes over instead
        assert result.matched
        assert result.decision is PolicyDecision.HALT


class TestRecoveryPolicyBundle:
    def test_build_recovery_policies(self):
        policies = build_recovery_policies()
        ids = {p.policy_id for p in policies}
        assert ids == {
            POSITION_RECOVERY_POLICY_ID,
            LEDGER_RECOVERY_POLICY_ID,
            EVENT_RECOVERY_POLICY_ID,
            GLOBAL_RECOVERY_POLICY_ID,
        }

    def test_register_recovery_policies_on_engine(self):
        engine = PolicyEngine()
        register_recovery_policies(engine)
        assert engine.policy_count == 4
        assert engine.get_policy(GLOBAL_RECOVERY_POLICY_ID) is not None

    def test_full_pipeline_position_failure(self):
        engine = PolicyEngine()
        register_recovery_policies(engine)
        evaluation = engine.evaluate(
            PolicyContext(position_integrity=RiskIntegrity.UNTRUSTED)
        )
        assert evaluation.decision is PolicyDecision.BLOCK
        start_recovery = [
            a for a in evaluation.actions if a.action_type is PolicyActionType.START_RECOVERY
        ]
        assert len(start_recovery) == 1
        assert start_recovery[0].target == "POSITION"
