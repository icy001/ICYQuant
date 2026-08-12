"""Tests for the incident command service (spec section 6)."""
from __future__ import annotations

import pytest

from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService
from services.control_plane.incident.command.command import (
    CommandStatus,
    CommandType,
)
from services.control_plane.incident.command.errors import CommandRejectedError
from services.control_plane.incident.command.service import IncidentCommandService
from services.control_plane.incident.incident_severity import IncidentSeverity


def _audit_service() -> IncidentAuditService:
    return IncidentAuditService(
        IncidentAuditRecorder(InMemoryIncidentAuditRepository())
    )


def test_low_severity_command_is_auto_approved(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.LOW)
    service = IncidentCommandService()

    command = service.create(
        incident,
        CommandType.ACKNOWLEDGE,
        requested_by="operator-1",
    )

    assert command.incident_id == incident.id
    assert command.command_type is CommandType.ACKNOWLEDGE
    assert command.status is CommandStatus.APPROVED


def test_medium_severity_allows_escalate(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.MEDIUM)
    service = IncidentCommandService()

    command = service.create(
        incident,
        CommandType.ESCALATE,
        requested_by="operator-1",
        reason="risk limit breached",
    )

    assert command.status is CommandStatus.APPROVED
    assert command.reason == "risk limit breached"


def test_critical_incident_requires_approval(incident_factory):
    """Key test: a CRITICAL command must stay PENDING until approved."""
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    service = IncidentCommandService()

    command = service.create(
        incident,
        CommandType.EXECUTE_MITIGATION,
        requested_by="operator-1",
    )

    assert command.status is CommandStatus.PENDING


def test_disallowed_command_is_rejected(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.LOW)
    service = IncidentCommandService()

    with pytest.raises(CommandRejectedError) as exc_info:
        service.create(
            incident,
            CommandType.ESCALATE,
            requested_by="operator-1",
        )

    assert "ESCALATE" in str(exc_info.value)
    assert "LOW" in str(exc_info.value)


def test_rejected_command_is_audited(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.LOW)
    audit = _audit_service()
    service = IncidentCommandService(audit_service=audit)

    with pytest.raises(CommandRejectedError):
        service.create(
            incident,
            CommandType.ESCALATE,
            requested_by="operator-1",
        )

    events = audit.timeline(incident.id)
    assert any(
        e.event_type is IncidentAuditEventType.COMMAND_REJECTED
        for e in events
    )


def test_created_command_is_audited(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.HIGH)
    audit = _audit_service()
    service = IncidentCommandService(audit_service=audit)

    command = service.create(
        incident,
        CommandType.EXECUTE_MITIGATION,
        requested_by="operator-1",
    )

    created = [
        e
        for e in audit.timeline(incident.id)
        if e.event_type is IncidentAuditEventType.COMMAND_CREATED
    ]
    assert len(created) == 1
    assert created[0].actor == "operator-1"
    assert created[0].command_id == command.command_id


def test_fatal_severity_is_gated_like_critical():
    """FATAL incidents (factory cannot build them via escalation defaults)
    must be gated behind approval just like CRITICAL."""
    class _StubIncident:
        def __init__(self, incident_id, severity):
            self.id = incident_id
            self.severity = severity

    incident = _StubIncident("INC-42", IncidentSeverity.FATAL)
    service = IncidentCommandService()

    command = service.create(
        incident,
        CommandType.ESCALATE,
        requested_by="risk-engine",
    )

    assert command.status is CommandStatus.PENDING


def test_high_severity_approval_chain(incident_factory):
    """Full HIGH-severity flow: create → approve → execute."""
    incident = incident_factory(severity=IncidentSeverity.HIGH)
    audit = _audit_service()
    service = IncidentCommandService(audit_service=audit)

    command = service.create(
        incident,
        CommandType.EXECUTE_MITIGATION,
        requested_by="operator-1",
    )
    assert command.status is CommandStatus.PENDING

    approval = service.approval_service.approve(
        command,
        approved_by="risk-manager-1",
        comment="reviewed, proceed",
    )
    assert command.status is CommandStatus.APPROVED
    assert approval.command_id == command.command_id

    types = [e.event_type for e in audit.timeline(incident.id)]
    assert IncidentAuditEventType.COMMAND_CREATED in types
    assert IncidentAuditEventType.COMMAND_APPROVED in types
