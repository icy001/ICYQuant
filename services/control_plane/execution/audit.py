"""
Execution Control audit — every state transition must produce an audit event
(Commit 26 Part 1.4, spec section 27):

    EXECUTION_PAUSED
    EXECUTION_DRAINING
    EXECUTION_DISABLED
    ...

Each event is correlated with the originating incident, the control that was
applied, the execution channel and the actor who performed the change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .state import ExecutionState


class ExecutionControlAuditEventType(str, Enum):

    EXECUTION_ACTIVE = "EXECUTION_ACTIVE"

    EXECUTION_DEGRADED = "EXECUTION_DEGRADED"

    EXECUTION_PAUSED = "EXECUTION_PAUSED"

    EXECUTION_DRAINING = "EXECUTION_DRAINING"

    EXECUTION_DISABLED = "EXECUTION_DISABLED"

    EXECUTION_FAILOVER = "EXECUTION_FAILOVER"


def audit_event_type_for(state: ExecutionState) -> ExecutionControlAuditEventType:
    """Map a target ExecutionState to the audit event it produces."""
    if state is ExecutionState.ACTIVE:
        return ExecutionControlAuditEventType.EXECUTION_ACTIVE
    if state is ExecutionState.DEGRADED:
        return ExecutionControlAuditEventType.EXECUTION_DEGRADED
    if state is ExecutionState.PAUSED:
        return ExecutionControlAuditEventType.EXECUTION_PAUSED
    if state is ExecutionState.DRAINING:
        return ExecutionControlAuditEventType.EXECUTION_DRAINING
    if state is ExecutionState.DISABLED:
        return ExecutionControlAuditEventType.EXECUTION_DISABLED
    return ExecutionControlAuditEventType.EXECUTION_FAILOVER


@dataclass(frozen=True)
class ExecutionControlAuditRecord:

    event_type: ExecutionControlAuditEventType

    execution_id: str

    previous_state: ExecutionState | None

    new_state: ExecutionState

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    venue: str | None = None

    actor: str = "execution-controller"

    reason: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
