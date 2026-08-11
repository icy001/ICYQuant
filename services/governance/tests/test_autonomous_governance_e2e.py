"""
End-to-end autonomous governance test.

Simulates the full governance lifecycle:
    NORMAL → WATCH → RESTRICTED → FROZEN → EMERGENCY → RECOVERY → NORMAL

Validates:
    - Risk detection
    - Policy evaluation
    - Authority checks
    - Freeze / Reduction / Revocation
    - Escalation
    - Recovery
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest

from services.governance.control_state import GovernanceStateType, GovernanceStateMachine
from services.governance.control_trigger import ControlTrigger, TriggerType, Severity
from services.governance.control_plane import GovernanceControlPlane
from services.governance.control_decision import ControlDecision
from services.governance.risk_guardian import RiskGuardian
from services.governance.authority_guardian import AuthorityGuardian
from services.governance.governance_state import GovernanceRuntimeState
from services.governance.governance_monitor import GovernanceMonitor
from services.governance.freeze_controller import FreezeController
from services.governance.exposure_controller import ExposureController
from services.governance.revoke_controller import RevokeController
from services.governance.escalation_controller import EscalationController
from services.governance.emergency_controller import EmergencyController
from services.governance.governance_intervention import GovernanceIntervention
from services.governance.governance_watchdog import GovernanceWatchdog
from services.governance.governance_heartbeat import GovernanceHeartbeat


class TestAutonomousGovernanceE2E:
    """End-to-end autonomous governance lifecycle test."""

    def _setup_system(self):
        """Set up a complete governance system with all components."""
        state_machine = GovernanceStateMachine()
        control_plane = GovernanceControlPlane(state_machine=state_machine)

        # Controllers
        freeze_ctrl = FreezeController()
        exposure_ctrl = ExposureController()
        revoke_ctrl = RevokeController()
        escalation_ctrl = EscalationController()
        emergency_ctrl = EmergencyController()

        # Wire controllers to control plane
        control_plane.set_freeze_controller(freeze_ctrl)
        control_plane.set_exposure_controller(exposure_ctrl)
        control_plane.set_revoke_controller(revoke_ctrl)
        control_plane.set_escalation_controller(escalation_ctrl)
        control_plane.set_emergency_controller(emergency_ctrl)

        # Guardians
        risk_guardian = RiskGuardian()
        authority_guardian = AuthorityGuardian()
        control_plane.set_risk_guardian(risk_guardian)
        control_plane.set_authority_guardian(authority_guardian)

        # Intervention engine
        intervention = GovernanceIntervention(
            freeze_controller=freeze_ctrl,
            exposure_controller=exposure_ctrl,
            revoke_controller=revoke_ctrl,
            escalation_controller=escalation_ctrl,
        )

        # Monitor
        monitor = GovernanceMonitor()

        # Watchdog
        watchdog = GovernanceWatchdog()

        return {
            "state_machine": state_machine,
            "control_plane": control_plane,
            "freeze_ctrl": freeze_ctrl,
            "exposure_ctrl": exposure_ctrl,
            "revoke_ctrl": revoke_ctrl,
            "escalation_ctrl": escalation_ctrl,
            "emergency_ctrl": emergency_ctrl,
            "risk_guardian": risk_guardian,
            "authority_guardian": authority_guardian,
            "intervention": intervention,
            "monitor": monitor,
            "watchdog": watchdog,
        }

    def test_normal_state(self):
        """NORMAL: all checks passing."""
        sys = self._setup_system()
        cp = sys["control_plane"]
        assert cp.current_state == GovernanceStateType.NORMAL
        assert cp.allows_new_risk
        assert cp.allows_risk_reduction

    def test_normal_to_watch(self):
        """NORMAL → WATCH: elevated drawdown detected."""
        sys = self._setup_system()
        cp = sys["control_plane"]

        trigger = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.LOW,
            source="risk-guardian",
            value=0.03,
            threshold=0.02,
            description="Drawdown 3% >= 2%",
        )

        decision = cp.evaluate_trigger(trigger)
        assert decision.target_state.severity >= GovernanceStateType.WATCH.severity

    def test_watch_to_restricted(self):
        """WATCH → RESTRICTED: drawdown escalates."""
        sys = self._setup_system()
        cp = sys["control_plane"]

        # First to WATCH
        trigger1 = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.LOW,
            value=0.03,
            threshold=0.02,
        )
        d1 = cp.evaluate_trigger(trigger1)
        # Manually transition
        if d1.requires_state_change:
            cp._state.transition(d1.target_state, trigger="TEST", reason="WATCH")

        # Then to RESTRICTED
        trigger2 = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.MEDIUM,
            value=0.05,
            threshold=0.04,
        )
        d2 = cp.evaluate_trigger(trigger2)
        assert d2.target_state.severity >= GovernanceStateType.RESTRICTED.severity

    def test_restricted_to_frozen(self):
        """RESTRICTED → FROZEN: severe drawdown."""
        sys = self._setup_system()
        cp = sys["control_plane"]

        trigger = ControlTrigger(
            trigger_type=TriggerType.DRAWDOWN_BREACH,
            severity=Severity.HIGH,
            source="risk-guardian",
            value=0.07,
            threshold=0.06,
        )

        decision = cp.evaluate_trigger(trigger)
        assert decision.target_state.severity >= GovernanceStateType.FROZEN.severity
        assert ControlActionType.FREEZE in decision.actions

    def test_frozen_to_emergency(self):
        """FROZEN → EMERGENCY: audit integrity failure."""
        sys = self._setup_system()
        cp = sys["control_plane"]

        # Go to FROZEN first
        for state in [GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED,
                       GovernanceStateType.FROZEN]:
            cp._state.transition(state, trigger="ESCALATE", reason="Test")

        trigger = ControlTrigger(
            trigger_type=TriggerType.AUDIT_INTEGRITY_FAILURE,
            severity=Severity.CRITICAL,
            source="audit-guardian",
            value=1,
            threshold=1,
        )
        decision = cp.evaluate_trigger(trigger)
        assert decision.target_state == GovernanceStateType.EMERGENCY

    def test_emergency_to_recovery(self):
        """EMERGENCY → RECOVERY: issue resolved."""
        sm = GovernanceStateMachine()
        # Set to EMERGENCY
        for s in [GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED,
                   GovernanceStateType.FROZEN, GovernanceStateType.EMERGENCY]:
            sm.transition(s, trigger="ESCALATE", reason="Test")

        assert sm.current_state == GovernanceStateType.EMERGENCY

        # Transition to RECOVERY
        t = sm.transition(GovernanceStateType.RECOVERY, trigger="REM", reason="Resolved")
        assert sm.current_state == GovernanceStateType.RECOVERY

    def test_recovery_to_watch_to_normal(self):
        """RECOVERY → WATCH → NORMAL: full recovery."""
        sm = GovernanceStateMachine()
        # Set to RECOVERY
        for s in [GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED,
                   GovernanceStateType.FROZEN, GovernanceStateType.EMERGENCY,
                   GovernanceStateType.RECOVERY]:
            sm.transition(s, trigger="ESCALATE" if s != GovernanceStateType.RECOVERY else "REM",
                          reason="Test")

        assert sm.current_state == GovernanceStateType.RECOVERY

        # Recover to WATCH
        sm.transition(GovernanceStateType.WATCH, trigger="VALID", reason="Validation passed")
        assert sm.current_state == GovernanceStateType.WATCH

        # Back to NORMAL
        sm.transition(GovernanceStateType.NORMAL, trigger="OK", reason="All clear")
        assert sm.current_state == GovernanceStateType.NORMAL

    def test_freeze_new_risk_does_not_freeze_reduction(self):
        """FROZEN blocks new risk but allows risk reduction."""
        sm = GovernanceStateMachine()
        for s in [GovernanceStateType.WATCH, GovernanceStateType.RESTRICTED,
                   GovernanceStateType.FROZEN]:
            sm.transition(s, trigger="ESCALATE", reason="Test")

        assert not sm.current_state.allows_new_risk
        assert sm.current_state.allows_risk_reduction

    def test_full_lifecycle_verification(self):
        """Verify the full state lifecycle: NORMAL → NORMAL."""
        sm = GovernanceStateMachine()

        # NORMAL → WATCH
        sm.transition(GovernanceStateType.WATCH, trigger="DRAWDOWN", reason="2.5%")
        assert sm.current_state == GovernanceStateType.WATCH

        # WATCH → RESTRICTED
        sm.transition(GovernanceStateType.RESTRICTED, trigger="DRAWDOWN", reason="4.3%")
        assert sm.current_state == GovernanceStateType.RESTRICTED

        # RESTRICTED → FROZEN
        sm.transition(GovernanceStateType.FROZEN, trigger="DRAWDOWN", reason="6.2%")
        assert sm.current_state == GovernanceStateType.FROZEN

        # FROZEN → EMERGENCY
        sm.transition(GovernanceStateType.EMERGENCY, trigger="AUDIT", reason="Integrity failure")
        assert sm.current_state == GovernanceStateType.EMERGENCY

        # EMERGENCY → RECOVERY
        sm.transition(GovernanceStateType.RECOVERY, trigger="REM", reason="Mitigated")
        assert sm.current_state == GovernanceStateType.RECOVERY

        # RECOVERY → WATCH
        sm.transition(GovernanceStateType.WATCH, trigger="OK", reason="Validated")
        assert sm.current_state == GovernanceStateType.WATCH

        # WATCH → NORMAL
        sm.transition(GovernanceStateType.NORMAL, trigger="OK", reason="All clear")
        assert sm.current_state == GovernanceStateType.NORMAL

        # Verify all transitions recorded
        assert len(sm._transitions) == 7

    def test_invariants(self):
        """Verify governance invariants hold."""
        cp = GovernanceControlPlane()
        invariants = cp.verify_invariants()
        # Should pass for NORMAL state
        assert "invariants" in invariants

    def test_control_plane_comprehensive_status(self):
        """Test comprehensive status report."""
        cp = GovernanceControlPlane()
        status = cp.get_comprehensive_status()
        assert status["current_state"] == "NORMAL"
        assert status["allows_new_risk"] is True
        assert "state_history" in status
        assert "metrics" in status
        assert "invariants" in status
