"""
CommandApproval — the authorization chain for high-severity control commands.

No high-severity control command may start without an explicit, auditable
approval (spec section 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from ..audit.event_type import IncidentAuditEventType
from .command import CommandStatus
from .errors import CommandApprovalError


@dataclass(frozen=True)
class CommandApproval:
    command_id: UUID
    approved_by: str

    approval_id: UUID = field(default_factory=uuid4)

    approved_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    comment: str = ""


class CommandApprovalService:
    """Approves PENDING commands and leaves an immutable authorization record.

    ``audit_service`` (optional) records a COMMAND_APPROVED event on the
    incident's audit chain so the authorization is fully attributable.
    """

    def __init__(self, audit_service: Any | None = None) -> None:
        self.audit_service = audit_service

    def approve(
        self,
        command,
        *,
        approved_by: str,
        comment: str = "",
    ) -> CommandApproval:
        if command.status is not CommandStatus.PENDING:
            raise CommandApprovalError(
                f"cannot approve command {command.command_id} in status "
                f"{command.status.value} (only PENDING commands can be approved)"
            )

        command.status = CommandStatus.APPROVED

        approval = CommandApproval(
            command_id=command.command_id,
            approved_by=approved_by,
            comment=comment,
        )

        if self.audit_service is not None:
            self.audit_service.record(
                command.incident_id,
                IncidentAuditEventType.COMMAND_APPROVED,
                actor=approved_by,
                payload={"comment": comment, "command_type": command.command_type.value},
                command_id=command.command_id,
            )

        return approval
