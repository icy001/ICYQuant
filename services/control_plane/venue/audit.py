"""
Venue Control audit — every major venue change must produce an audit event
(Commit 26 Part 1.4, spec section 27):

    VENUE_DEGRADED
    VENUE_PAUSED
    VENUE_DISABLED
    VENUE_FAILOVER_STARTED
    VENUE_FAILOVER_COMPLETED
    VENUE_RECOVERED
    ...

Each event is correlated with the originating incident, the venue, the
control, the actor and the reason — so the system can answer
"why was this order rerouted from NASDAQ to NYSE?".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from .state import VenueState


class VenueControlAuditEventType(str, Enum):

    VENUE_DEGRADED = "VENUE_DEGRADED"

    VENUE_PAUSED = "VENUE_PAUSED"

    VENUE_DISABLED = "VENUE_DISABLED"

    VENUE_FAILOVER_STARTED = "VENUE_FAILOVER_STARTED"

    VENUE_FAILOVER_COMPLETED = "VENUE_FAILOVER_COMPLETED"

    VENUE_RECOVERED = "VENUE_RECOVERED"

    VENUE_UNKNOWN = "VENUE_UNKNOWN"


def audit_event_type_for(
    previous_state: VenueState | None,
    new_state: VenueState,
) -> VenueControlAuditEventType:
    """Map a state transition to the audit event it produces."""
    if new_state is VenueState.FAILOVER:
        return VenueControlAuditEventType.VENUE_FAILOVER_STARTED
    if (
        previous_state is VenueState.FAILOVER
        and new_state is VenueState.ONLINE
    ):
        return VenueControlAuditEventType.VENUE_FAILOVER_COMPLETED
    if new_state is VenueState.ONLINE:
        return VenueControlAuditEventType.VENUE_RECOVERED
    if new_state is VenueState.DEGRADED:
        return VenueControlAuditEventType.VENUE_DEGRADED
    if new_state is VenueState.PAUSED:
        return VenueControlAuditEventType.VENUE_PAUSED
    if new_state is VenueState.DISABLED:
        return VenueControlAuditEventType.VENUE_DISABLED
    return VenueControlAuditEventType.VENUE_UNKNOWN


@dataclass(frozen=True)
class VenueControlAuditRecord:

    event_type: VenueControlAuditEventType

    venue: str

    previous_state: VenueState | None

    new_state: VenueState

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    execution_id: str | None = None

    actor: str = "venue-controller"

    reason: str = ""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
