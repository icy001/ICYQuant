"""
Global Control audit — every major global change must produce an audit event
(Commit 26 Part 1.5, spec section 30):

    GLOBAL_KILL_ACTIVATED
    GLOBAL_RESTRICTION_ENABLED
    RECOVERY_STARTED
    RECOVERY_COMPLETED

Each event is correlated with the originating incident, the control, the
actor, the reason, the system state and the previous/new global state —
so the system can answer "who killed the market, when and why?".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .state import GlobalControlState


class GlobalControlAuditEventType(str, Enum):

    GLOBAL_RESTRICTION_ENABLED = "GLOBAL_RESTRICTION_ENABLED"

    GLOBAL_KILL_ACTIVATED = "GLOBAL_KILL_ACTIVATED"

    RECOVERY_STARTED = "RECOVERY_STARTED"

    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"


def audit_event_type_for(
    previous_state: GlobalControlState | None,
    new_state: GlobalControlState,
) -> GlobalControlAuditEventType:
    """Map a global state transition to the audit event it produces."""
    if new_state is GlobalControlState.RESTRICTED:
        return GlobalControlAuditEventType.GLOBAL_RESTRICTION_ENABLED
    if new_state is GlobalControlState.KILLED:
        return GlobalControlAuditEventType.GLOBAL_KILL_ACTIVATED
    if new_state is GlobalControlState.RECOVERY:
        return GlobalControlAuditEventType.RECOVERY_STARTED
    if new_state is GlobalControlState.NORMAL:
        return GlobalControlAuditEventType.RECOVERY_COMPLETED
    return GlobalControlAuditEventType.GLOBAL_KILL_ACTIVATED


@dataclass(frozen=True)
class GlobalControlAuditRecord:

    event_type: GlobalControlAuditEventType

    previous_state: GlobalControlState | None

    new_state: GlobalControlState

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    actor: str = "global-controller"

    reason: str = ""

    system_state: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
