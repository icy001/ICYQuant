"""Test Emergency Controller — emergency mode behavior."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.emergency_state import EmergencyState, EmergencyStateType
from services.governance.emergency_action import EmergencyAction, EmergencyActionType
from services.governance.emergency_policy import EmergencyPolicy, STANDARD_EMERGENCY_POLICY
from services.governance.emergency_controller import EmergencyController


class TestEmergencyState:
    """Test emergency state machine."""

    def test_initial_state(self):
        es = EmergencyState()
        assert es.state == EmergencyStateType.NONE
        assert not es.is_active

    def test_activate(self):
        es = EmergencyState()
        es.activate("AUDIT_INTEGRITY_FAILURE", "Hash chain broken.")
        assert es.state == EmergencyStateType.ACTIVATED
        assert es.is_active

    def test_escalate(self):
        es = EmergencyState()
        es.activate("TEST", "Test")
        es.escalate("Cannot auto-resolve.")
        assert es.state == EmergencyStateType.ESCALATED

    def test_resolve(self):
        es = EmergencyState()
        es.activate("TEST", "Test")
        es.resolve()
        assert es.state == EmergencyStateType.RESOLVED
        assert not es.is_active

    def test_duration(self):
        es = EmergencyState()
        es.activate("TEST", "Test")
        assert es.duration_seconds > 0


class TestEmergencyPolicy:
    """Test emergency policy constraints."""

    def test_allows_risk_reducing_actions(self):
        policy = STANDARD_EMERGENCY_POLICY
        assert policy.is_allowed(EmergencyActionType.FREEZE_ALL)
        assert policy.is_allowed(EmergencyActionType.REDUCE_EXPOSURE)
        assert policy.is_allowed(EmergencyActionType.REVOKE_AUTHORITY)

    def test_forbids_risk_increasing_actions(self):
        policy = STANDARD_EMERGENCY_POLICY
        assert policy.is_forbidden_command("INCREASE_RISK")
        assert policy.is_forbidden_command("NEW_ALLOCATION")
        assert policy.is_forbidden_command("INCREASE_LEVERAGE")


class TestEmergencyController:
    """Test emergency controller behavior."""

    def test_activate_emergency(self):
        ec = EmergencyController()
        result = ec.activate(reason="Audit failure detected.")
        assert result["status"] == "ACTIVATED"
        assert ec.is_active

    def test_cannot_activate_twice(self):
        ec = EmergencyController()
        ec.activate(reason="Test")
        result = ec.activate(reason="Test again")
        assert result["status"] == "ALREADY_ACTIVE"

    def test_deactivate(self):
        ec = EmergencyController()
        ec.activate(reason="Test")
        result = ec.deactivate(reason="Resolved.")
        assert result["status"] == "RESOLVED"
        assert not ec.is_active

    def test_cannot_act_when_inactive(self):
        ec = EmergencyController()
        result = ec.freeze_all(reason="Test")
        assert result["status"] == "EMERGENCY_NOT_ACTIVE"

    def test_escalate(self):
        ec = EmergencyController()
        ec.activate(reason="Test")
        result = ec.escalate(reason="Need human intervention.")
        assert result["status"] == "EXECUTED"

    def test_metrics(self):
        ec = EmergencyController()
        ec.activate(reason="Test")
        metrics = ec.get_metrics()
        assert metrics["is_active"]
        assert metrics["escalation_level"] == 0
