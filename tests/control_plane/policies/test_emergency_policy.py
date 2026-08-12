"""Unit tests: global-emergency-policy."""

from __future__ import annotations

from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.policies.emergency_policy import (
    POLICY_ID,
    build_emergency_policy,
)
from services.control_plane.policy.policy_action import PolicyActionType
from services.control_plane.policy.policy_context import (
    KillSwitchState,
    PolicyContext,
)
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.policy.policy_priority import PolicyPriority


def _engine() -> PolicyEngine:
    engine = PolicyEngine()
    engine.register_policy(build_emergency_policy())
    return engine


class TestEmergencyPolicy:
    def test_emergency_mode_global_kill(self):
        evaluation = _engine().evaluate(
            PolicyContext(operational_state=OperationalState.EMERGENCY)
        )
        assert evaluation.decision is PolicyDecision.ESCALATE
        assert evaluation.priority is PolicyPriority.CRITICAL
        assert "emergency-mode-global-kill" in evaluation.matched_rules
        types = {a.action_type for a in evaluation.actions}
        assert PolicyActionType.ACTIVATE_KILL_SWITCH in types
        assert PolicyActionType.HALT_TRADING in types
        assert PolicyActionType.ESCALATE_INCIDENT in types

    def test_global_kill_active_halts(self):
        evaluation = _engine().evaluate(
            PolicyContext(
                kill_switch_state=KillSwitchState.ACTIVE,
                kill_switch_scope="GLOBAL",
            )
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert evaluation.reasons == ["GLOBAL_KILL_ACTIVE"]

    def test_scoped_kill_does_not_trigger_global_halt(self):
        evaluation = _engine().evaluate(
            PolicyContext(
                kill_switch_state=KillSwitchState.ACTIVE,
                kill_switch_scope="STRATEGY",
            )
        )
        assert "global-kill-active-halt" not in evaluation.matched_rules

    def test_multiple_critical_components_kill(self):
        evaluation = _engine().evaluate(
            PolicyContext(critical_unhealthy_components=2)
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert "multiple-critical-failures-kill" in evaluation.matched_rules
        assert PolicyActionType.ACTIVATE_KILL_SWITCH in {
            a.action_type for a in evaluation.actions
        }

    def test_single_critical_component_not_killed(self):
        evaluation = _engine().evaluate(
            PolicyContext(critical_unhealthy_components=1)
        )
        assert "multiple-critical-failures-kill" not in evaluation.matched_rules

    def test_risk_integrity_untrusted_kills(self):
        evaluation = _engine().evaluate(
            PolicyContext(risk_integrity="UNTRUSTED")
        )
        assert "risk-integrity-emergency-kill" in evaluation.matched_rules
        assert PolicyActionType.ACTIVATE_KILL_SWITCH in {
            a.action_type for a in evaluation.actions
        }

    def test_healthy_context_not_fired(self):
        evaluation = _engine().evaluate(PolicyContext())
        assert evaluation.matched_policies == []
        assert evaluation.decision is PolicyDecision.ALLOW

    def test_policy_id(self):
        assert build_emergency_policy().policy_id == POLICY_ID
