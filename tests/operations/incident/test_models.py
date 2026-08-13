"""Incident auxiliary models tests (Commit 27 Part 1.4, spec sections 23-25, 30-31)."""

from __future__ import annotations

from services.operations import (
    RECOVERY_GATE_CHECKS,
    IncidentControlRequest,
    RecoveryCheck,
    RecoveryGate,
)


def test_control_request_defaults():

    request = IncidentControlRequest(
        incident_id="INC-123",
        action="PAUSE_TRADING",
        reason="Position / Ledger mismatch",
        requested_by="incident-engine",
    )

    assert request.incident_id == "INC-123"
    assert request.action == "PAUSE_TRADING"
    assert request.reason == "Position / Ledger mismatch"
    assert request.requested_by == "incident-engine"
    assert request.requires_confirmation is True


def test_control_request_custom_confirmation():

    request = IncidentControlRequest(
        incident_id="INC-123",
        action="GLOBAL_KILL",
        reason="global trading safety compromised",
        requested_by="risk-manager",
        requires_confirmation=False,
    )

    assert request.requires_confirmation is False


def test_recovery_gate_requires_all_checks():

    gate = RecoveryGate()

    results = {
        "service_health": True,
        "risk_state": True,
        "position_state": True,
        "ledger_state": True,
        "reconciliation": True,
        "execution": True,
        # venue missing -> FAIL
    }

    assert gate.evaluate(results) is False


def test_recovery_gate_any_failure_blocks_resolution():

    gate = RecoveryGate()

    results = {
        "service_health": True,
        "risk_state": True,
        "position_state": True,
        "ledger_state": True,
        "reconciliation": False,
        "execution": True,
        "venue": True,
    }

    assert gate.evaluate(results) is False


def test_recovery_gate_all_pass():

    gate = RecoveryGate()

    results = {
        "service_health": True,
        "risk_state": True,
        "position_state": True,
        "ledger_state": True,
        "reconciliation": True,
        "execution": True,
        "venue": True,
    }

    assert gate.evaluate(results) is True


def test_recovery_gate_checks_report_missing_as_failed():

    gate = RecoveryGate()

    checks = gate.checks({})

    assert len(checks) == len(RECOVERY_GATE_CHECKS)
    assert all(isinstance(check, RecoveryCheck) for check in checks)
    assert all(check.passed is False for check in checks)


def test_recovery_gate_check_names():

    assert RECOVERY_GATE_CHECKS == (
        "service_health",
        "risk_state",
        "position_state",
        "ledger_state",
        "reconciliation",
        "execution",
        "venue",
    )
