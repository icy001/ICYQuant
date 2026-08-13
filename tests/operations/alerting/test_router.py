"""
Tests for AlertRouter (Commit 27 Part 1.3, spec sections 16-17, 34-35).

    Severity       Destination
    ────────────────────────────────
    INFO           Dashboard
    WARNING        Operations
    ERROR          Operations On-Call
    CRITICAL       Incident On-Call
    EMERGENCY      Emergency On-Call
"""

from __future__ import annotations

from services.operations import (
    AlertRouter,
    AlertSeverity,
)


def test_info_routes_to_dashboard():
    router = AlertRouter()

    assert router.route(AlertSeverity.INFO) == "dashboard"


def test_warning_routes_to_operations():
    router = AlertRouter()

    assert router.route(AlertSeverity.WARNING) == "operations"


def test_error_routes_to_operations_oncall():
    router = AlertRouter()

    assert router.route(AlertSeverity.ERROR) == "operations_oncall"


def test_critical_routes_to_incident_oncall():
    """spec section 34: CRITICAL -> incident_oncall。"""
    router = AlertRouter()

    assert router.route(
        AlertSeverity.CRITICAL
    ) == "incident_oncall"


def test_emergency_routes_to_emergency_oncall():
    """spec section 35: EMERGENCY -> emergency_oncall。"""
    router = AlertRouter()

    assert router.route(
        AlertSeverity.EMERGENCY
    ) == "emergency_oncall"
