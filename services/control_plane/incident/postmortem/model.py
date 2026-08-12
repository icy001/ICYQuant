"""
IncidentPostmortem — the aggregate postmortem document.

Holds the structured root cause, impact assessment, auto-built timeline and
remediation action items.  ``incident_id`` is the string form of the incident
identifier (``IncidentId.value``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from .action_item import RemediationActionItem
from .impact import IncidentImpact
from .root_cause import RootCause
from .status import PostmortemStatus
from .timeline import TimelineEntry


@dataclass
class IncidentPostmortem:

    incident_id: str
    title: str

    postmortem_id: UUID = field(default_factory=uuid4)
    status: PostmortemStatus = PostmortemStatus.DRAFT

    summary: str = ""
    root_cause: Optional[RootCause] = None
    impact: Optional[IncidentImpact] = None
    timeline: List[TimelineEntry] = field(default_factory=list)
    action_items: List[RemediationActionItem] = field(default_factory=list)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: Optional[datetime] = None
