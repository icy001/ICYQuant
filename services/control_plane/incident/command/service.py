"""
IncidentCommandService — create and gate control commands against policy.

Commands are the single admission point for control actions: every action a
human or system wants to take on an incident must first pass through
create() → policy check → approval gate (spec section 6).
"""

from __future__ import annotations

from typing import Any, Optional

from ..audit.event_type import IncidentAuditEventType
from .approval import CommandApproval, CommandApprovalService
from .command import CommandStatus, CommandType, IncidentCommand
from .errors import CommandRejectedError
from .policy import DEFAULT_COMMAND_POLICIES


class IncidentCommandService:
    """Creates commands under the severity CommandPolicy.

    ``audit_service`` (optional) records COMMAND_CREATED / COMMAND_REJECTED
    events on the incident's audit chain.
    """

    def __init__(
        self,
        audit_service: Any | None = None,
        approval_service: CommandApprovalService | None = None,
    ) -> None:
        self.audit_service = audit_service
        self.approval_service = approval_service or CommandApprovalService(
            audit_service=audit_service
        )

    def create(
        self,
        incident,
        command_type: CommandType,
        *,
        requested_by: str,
        reason: str = "",
        metadata: dict | None = None,
    ) -> IncidentCommand:
        policy = DEFAULT_COMMAND_POLICIES[incident.severity]

        if command_type not in policy.allowed_commands:
            if self.audit_service is not None:
                self.audit_service.record(
                    incident.id,
                    IncidentAuditEventType.COMMAND_REJECTED,
                    actor=requested_by,
                    payload={
                        "command_type": command_type.value,
                        "reason": reason,
                        "severity": incident.severity.value,
                    },
                )
            raise CommandRejectedError(
                f"command {command_type.value} is not allowed for severity "
                f"{incident.severity.value}"
            )

        command = IncidentCommand(
            incident_id=incident.id,
            command_type=command_type,
            requested_by=requested_by,
            reason=reason,
            metadata=metadata or {},
        )

        # Low severity commands are auto-approved by policy.
        if not policy.approval_required:
            command.status = CommandStatus.APPROVED

        if self.audit_service is not None:
            self.audit_service.record(
                incident.id,
                IncidentAuditEventType.COMMAND_CREATED,
                actor=requested_by,
                payload={
                    "command_type": command_type.value,
                    "reason": reason,
                    "approval_required": policy.approval_required,
                },
                command_id=command.command_id,
            )

        return command
