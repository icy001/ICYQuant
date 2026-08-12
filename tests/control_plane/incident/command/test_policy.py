"""Tests for the command policy (spec section 4)."""
from __future__ import annotations

from services.control_plane.incident.command.command import CommandType
from services.control_plane.incident.command.policy import (
    DEFAULT_COMMAND_POLICIES,
    CommandPolicy,
)
from services.control_plane.incident.incident_severity import IncidentSeverity


def test_low_severity_has_base_commands_only():
    policy = DEFAULT_COMMAND_POLICIES[IncidentSeverity.LOW]

    assert CommandType.ACKNOWLEDGE in policy.allowed_commands
    assert CommandType.START_MITIGATION in policy.allowed_commands
    assert CommandType.RESOLVE in policy.allowed_commands
    assert CommandType.CLOSE in policy.allowed_commands
    assert CommandType.REOPEN in policy.allowed_commands
    assert not policy.approval_required


def test_low_severity_rejects_operational_commands():
    policy = DEFAULT_COMMAND_POLICIES[IncidentSeverity.LOW]

    assert CommandType.EXECUTE_MITIGATION not in policy.allowed_commands
    assert CommandType.ESCALATE not in policy.allowed_commands


def test_medium_severity_allows_operational_commands():
    policy = DEFAULT_COMMAND_POLICIES[IncidentSeverity.MEDIUM]

    assert CommandType.EXECUTE_MITIGATION in policy.allowed_commands
    assert CommandType.ESCALATE in policy.allowed_commands
    assert not policy.approval_required


def test_high_critical_fatal_require_approval():
    for severity in (
        IncidentSeverity.HIGH,
        IncidentSeverity.CRITICAL,
        IncidentSeverity.FATAL,
    ):
        policy = DEFAULT_COMMAND_POLICIES[severity]
        assert policy.approval_required is True, severity
        assert CommandType.EXECUTE_MITIGATION in policy.allowed_commands
        assert CommandType.ESCALATE in policy.allowed_commands


def test_every_severity_has_a_policy():
    for severity in IncidentSeverity:
        assert isinstance(
            DEFAULT_COMMAND_POLICIES[severity],
            CommandPolicy,
        ), severity


def test_policy_is_frozen_and_immutable():
    policy = DEFAULT_COMMAND_POLICIES[IncidentSeverity.LOW]
    assert isinstance(policy, CommandPolicy)
    try:
        policy.approval_required = True  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert isinstance(exc, (AttributeError, TypeError))
    else:  # pragma: no cover
        raise AssertionError("frozen dataclass must reject attribute assignment")
