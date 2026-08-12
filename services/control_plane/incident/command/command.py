"""
IncidentCommand — the unified entry point for control actions on an incident.

Every control action (acknowledge, mitigate, escalate, resolve, ...) is
requested as a command first, then validated by the CommandPolicy and gated by
the approval chain (spec section 3/4/5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .errors import CommandError


class CommandType(str, Enum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    START_MITIGATION = "START_MITIGATION"
    EXECUTE_MITIGATION = "EXECUTE_MITIGATION"
    ESCALATE = "ESCALATE"
    RESOLVE = "RESOLVE"
    CLOSE = "CLOSE"
    REOPEN = "REOPEN"


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class IncidentCommand:
    incident_id: str
    command_type: CommandType
    requested_by: str

    command_id: UUID = field(default_factory=uuid4)

    status: CommandStatus = CommandStatus.PENDING

    reason: str = ""

    requested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    executed_at: datetime | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    # -- status transitions ---------------------------------------------

    def mark_executing(self) -> None:
        if self.status is not CommandStatus.APPROVED:
            raise CommandError(
                f"cannot execute command {self.command_id} in status "
                f"{self.status.value} (only APPROVED commands can execute)"
            )
        self.status = CommandStatus.EXECUTING

    def mark_succeeded(self) -> None:
        self.status = CommandStatus.SUCCEEDED
        self.executed_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.status = CommandStatus.FAILED
        self.executed_at = datetime.now(timezone.utc)

    def mark_rejected(self) -> None:
        self.status = CommandStatus.REJECTED
