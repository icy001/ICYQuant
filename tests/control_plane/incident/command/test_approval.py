"""Tests for the command approval chain (spec section 5)."""
from __future__ import annotations

from uuid import UUID

import pytest

from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService
from services.control_plane.incident.command.approval import (
    CommandApproval,
    CommandApprovalService,
)
from services.control_plane.incident.command.command import (
    CommandStatus,
    CommandType,
    IncidentCommand,
)
from services.control_plane.incident.command.errors import CommandApprovalError


def _audit_service() -> IncidentAuditService:
    return IncidentAuditService(
        IncidentAuditRecorder(InMemoryIncidentAuditRepository())
    )


def _pending_command(**kwargs):
    return IncidentCommand(
        incident_id=kwargs.pop("incident_id", "INC-1"),
        command_type=kwargs.pop(
            "command_type", CommandType.EXECUTE_MITIGATION
        ),
        requested_by=kwargs.pop("requested_by", "operator-1"),
        **kwargs,
    )


def test_approve_sets_status_and_returns_approval():
    service = CommandApprovalService()
    command = _pending_command()

    approval = service.approve(
        command,
        approved_by="risk-manager-1",
        comment="approved after review",
    )

    assert command.status is CommandStatus.APPROVED
    assert isinstance(approval, CommandApproval)
    assert approval.command_id == command.command_id
    assert approval.approved_by == "risk-manager-1"
    assert approval.comment == "approved after review"
    assert isinstance(approval.approval_id, UUID)
    assert approval.approved_at is not None


def test_approve_rejects_non_pending_command():
    service = CommandApprovalService()
    command = _pending_command(status=CommandStatus.EXECUTING)

    with pytest.raises(CommandApprovalError):
        service.approve(command, approved_by="risk-manager-1")


def test_approve_is_auditable():
    audit = _audit_service()
    service = CommandApprovalService(audit_service=audit)
    command = _pending_command()

    service.approve(command, approved_by="risk-manager-1")

    event_types = [e.event_type for e in audit.timeline(command.incident_id)]
    assert IncidentAuditEventType.COMMAND_APPROVED in event_types
    approved = [
        e
        for e in audit.timeline(command.incident_id)
        if e.event_type is IncidentAuditEventType.COMMAND_APPROVED
    ][0]
    assert approved.actor == "risk-manager-1"
    assert approved.command_id == command.command_id


def test_approval_is_frozen():
    approval = CommandApproval(
        command_id=UUID(int=1),
        approved_by="risk-manager-1",
    )
    try:
        approval.approved_by = "someone-else"  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert isinstance(exc, (AttributeError, TypeError))
    else:  # pragma: no cover
        raise AssertionError("frozen dataclass must reject attribute assignment")
