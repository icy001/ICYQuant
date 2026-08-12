"""
RemediationActionItem — a tracked remediation task produced by a postmortem.

Every action item must carry an owner, a status and a due date; completion is
a first-class state so remediation can never silently stall
(spec sections 12/19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ActionItemStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class RemediationActionItem:

    title: str
    owner: str

    action_item_id: UUID = field(default_factory=uuid4)
    description: str = ""
    status: ActionItemStatus = ActionItemStatus.OPEN
    due_at: Optional[str] = None
    linked_incident_id: Optional[UUID] = None
