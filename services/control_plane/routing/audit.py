"""
Routing Control audit — every routing decision must be traceable
(Commit 26 Part 1.4, spec section 27):

    ROUTE_BLOCKED
    ROUTE_REDIRECTED
    ROUTE_ALLOWED

This answers the question "why was this order rerouted from NASDAQ to NYSE?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class RoutingAuditEventType(str, Enum):

    ROUTE_ALLOWED = "ROUTE_ALLOWED"

    ROUTE_BLOCKED = "ROUTE_BLOCKED"

    ROUTE_REDIRECTED = "ROUTE_REDIRECTED"


@dataclass(frozen=True)
class RoutingAuditRecord:

    event_type: RoutingAuditEventType

    venues: tuple[str, ...]

    selected_venue: str | None

    fallback_venue: str | None

    reason: str

    record_id: UUID = field(default_factory=uuid4)

    incident_id: UUID | None = None

    control_id: UUID | None = None

    execution_id: str | None = None

    actor: str = "routing-controller"

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
