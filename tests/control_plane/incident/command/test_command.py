"""Tests for the incident command model (spec section 3)."""
from __future__ import annotations

from uuid import UUID

from services.control_plane.incident.command.command import (
    CommandStatus,
    CommandType,
    IncidentCommand,
)


def test_command_defaults():
    command = IncidentCommand(
        incident_id="INC-1",
        command_type=CommandType.ACKNOWLEDGE,
        requested_by="operator-1",
    )

    assert command.incident_id == "INC-1"
    assert isinstance(command.command_id, UUID)
    assert command.status is CommandStatus.PENDING
    assert command.reason == ""
    assert command.metadata == {}
    assert command.executed_at is None


def test_command_type_values():
    assert CommandType.ACKNOWLEDGE.value == "ACKNOWLEDGE"
    assert CommandType.START_MITIGATION.value == "START_MITIGATION"
    assert CommandType.EXECUTE_MITIGATION.value == "EXECUTE_MITIGATION"
    assert CommandType.ESCALATE.value == "ESCALATE"
    assert CommandType.RESOLVE.value == "RESOLVE"
    assert CommandType.CLOSE.value == "CLOSE"
    assert CommandType.REOPEN.value == "REOPEN"


def test_command_status_values():
    assert CommandStatus.PENDING.value == "PENDING"
    assert CommandStatus.APPROVED.value == "APPROVED"
    assert CommandStatus.EXECUTING.value == "EXECUTING"
    assert CommandStatus.SUCCEEDED.value == "SUCCEEDED"
    assert CommandStatus.FAILED.value == "FAILED"
    assert CommandStatus.REJECTED.value == "REJECTED"


def test_command_execution_transitions():
    command = IncidentCommand(
        incident_id="INC-1",
        command_type=CommandType.START_MITIGATION,
        requested_by="operator-1",
        status=CommandStatus.APPROVED,
    )

    command.mark_executing()
    assert command.status is CommandStatus.EXECUTING

    command.mark_succeeded()
    assert command.status is CommandStatus.SUCCEEDED
    assert command.executed_at is not None


def test_command_mark_executing_requires_approved():
    command = IncidentCommand(
        incident_id="INC-1",
        command_type=CommandType.START_MITIGATION,
        requested_by="operator-1",
    )

    try:
        command.mark_executing()
    except Exception as exc:  # noqa: BLE001
        assert "only APPROVED commands can execute" in str(exc)
        assert command.status is CommandStatus.PENDING
    else:  # pragma: no cover
        raise AssertionError("mark_executing should refuse a PENDING command")
