"""Test Control Plane — governance control plane core operations."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.control_state import (
    GovernanceStateType, GovernanceStateMachine, GovernanceStateTransition,
)
from services.governance.control_action import ControlActionType
from services.governance.control_trigger import ControlTrigger, TriggerType, Severity
from services.governance.control_condition import ControlCondition, STANDARD_CONTROL_CONDITIONS
from services.governance.control_policy import ControlPolicy
from services.governance.control_decision import ControlDecision
from services.governance.control_plane import GovernanceControlPlane


class TestGovernanceStateMachine:
    """Test state machine behavior."""

    def test_initial_state_is_normal(self):
        sm = GovernanceStateMachine()
        assert sm.current_state == GovernanceStateType.NORMAL

    def test_valid_transition(self):
        sm = GovernanceStateMachine()
        t = sm.transition(GovernanceStateType.WATCH, trigger="TEST", reason="Test")
        assert sm.current_state == GovernanceStateType.WATCH
        assert t.from_state == GovernanceStateType.NORMAL
        assert t.to_state == GovernanceStateType.WATCH

    def test_invalid_transition_raises(self):
        sm = GovernanceStateMachine()
        with pytest.raises(ValueError):
            sm.transition(GovernanceStateType.RECOVERY, trigger="TEST")

    def test_state_properties(self):
        sm = GovernanceStateMachine()
        assert sm.is_normal
        assert not sm.is_elevated
        assert not sm.is_critical
        assert sm.current_state.allows_new_risk
        assert sm.current_state.allows_risk_reduction

    def test_frozen_blocks_new_risk(self):
        sm = GovernanceStateMachine()
        sm.transition(GovernanceStateType.WATCH, trigger="T")
        sm.transition(GovernanceStateType.RESTRICTED, trigger="T")
        sm.transition(GovernanceStateType.FROZEN, trigger="T")
        assert not sm.current_state.allows_new_risk
        assert sm.current_state.allows_risk_reduction

    def test_emergency_to_recovery_to_watch(self):
        sm = GovernanceStateMachine()
        for state in [GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED,
                       GovernanceStateType.FROZEN, GovernanceStateType.EMERGENCY]:
            sm.transition(state, trigger="ESCALATE")
        sm.transition(GovernanceStateType.RECOVERY, trigger="REM")
        sm.transition(GovernanceStateType.WATCH, trigger="REM")
        assert sm.current_state == GovernanceStateType.WATCH


class TestControlPlane:
    """Test governance control plane."""

    def test_initial_state(self):
        cp = GovernanceControlPlane()
        assert cp.current_state == GovernanceStateType.NORMAL
        assert cp.allows_new_risk

    def test_evaluate_trigger_drawdown_watch(self):
        cp = GovernanceControlPlane()
        trigger = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.LOW,
            source="test",
            description="Test drawdown",
            value=0.03,
            threshold=0.02,
        )
        decision = cp.evaluate_trigger(trigger)
        assert decision.target_state in (GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED)

    def test_evaluate_trigger_drawdown_freeze(self):
        cp = GovernanceControlPlane()
        trigger = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.HIGH,
            source="test",
            description="Severe drawdown",
            value=0.07,
            threshold=0.06,
        )
        decision = cp.evaluate_trigger(trigger)
        # The highest priority freeze condition should match
        assert any(a in (ControlActionType.FREEZE, ControlActionType.CANCEL)
                   for a in decision.actions)

    def test_evaluate_no_trigger_returns_allow(self):
        cp = GovernanceControlPlane()
        trigger = ControlTrigger(
            trigger_type=TriggerType.POLICY_BREACH,
            severity=Severity.INFO,
            source="test",
            value=0.001,
            threshold=0.01,
        )
        decision = cp.evaluate_trigger(trigger)
        assert ControlActionType.ALLOW in decision.actions

    def test_control_decision_allow(self):
        d = ControlDecision.allow("All clear.")
        assert ControlActionType.ALLOW in d.actions
        assert not d.requires_state_change

    def test_control_decision_freeze(self):
        d = ControlDecision.freeze(
            reason="Drawdown too high.",
            current_state=GovernanceStateType.RESTRICTED,
        )
        assert ControlActionType.FREEZE in d.actions
        assert d.target_state == GovernanceStateType.FROZEN

    def test_control_decision_emergency(self):
        d = ControlDecision.emergency(
            reason="Audit integrity failure.",
            current_state=GovernanceStateType.FROZEN,
        )
        assert ControlActionType.EMERGENCY in d.actions
        assert d.target_state == GovernanceStateType.EMERGENCY

    def test_verify_invariants(self):
        cp = GovernanceControlPlane()
        result = cp.verify_invariants()
        assert "invariants" in result

    def test_run_cycle_no_triggers(self):
        cp = GovernanceControlPlane()
        result = cp.run_cycle(triggers=[])
        assert result["state_before"] == "NORMAL"
        assert result["state_after"] == "NORMAL"
        assert not result["state_changed"]

    def test_add_custom_condition(self):
        cp = GovernanceControlPlane()
        cond = ControlCondition(
            condition_id="COND-CUSTOM",
            trigger_type=TriggerType.POLICY_BREACH,
            threshold_value=100,
            target_state=GovernanceStateType.WATCH,
            actions=[ControlActionType.WARN],
            priority=99,
        )
        cp.add_condition(cond)
        trigger = ControlTrigger(
            trigger_type=TriggerType.POLICY_BREACH,
            severity=Severity.MEDIUM,
            value=150,
            threshold=100,
        )
        decision = cp.evaluate_trigger(trigger)
        assert ControlActionType.WARN in decision.actions


class TestControlDecision:
    """Test control decision factory methods."""

    def test_warn_decision(self):
        d = ControlDecision.warn("Risk elevated.")
        assert d.target_state == GovernanceStateType.WATCH
        assert ControlActionType.WARN in d.actions

    def test_restrict_decision(self):
        d = ControlDecision.restrict("Exposure high.", current_state=GovernanceStateType.WATCH)
        assert d.target_state == GovernanceStateType.RESTRICTED
        assert ControlActionType.RESTRICT in d.actions

    def test_revoke_decision(self):
        d = ControlDecision.revoke("Authority compromised.", target="AUTH-001")
        assert ControlActionType.REVOKE in d.actions
        assert d.metadata["revoke_target"] == "AUTH-001"

    def test_recover_decision(self):
        d = ControlDecision.recover(
            "System stabilized.",
            current_state=GovernanceStateType.EMERGENCY,
        )
        assert d.target_state == GovernanceStateType.RECOVERY
        assert ControlActionType.RECOVER in d.actions
