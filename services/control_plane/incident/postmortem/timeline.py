"""
IncidentTimelineBuilder — reconstruct the incident timeline from audit events.

The postmortem timeline is not typed in by hand: it is derived automatically
from the audit trail, so the incident's story can never drift from what the
system actually recorded (spec section 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List
from uuid import UUID


@dataclass(frozen=True)
class TimelineEntry:

    timestamp: datetime
    event_id: UUID
    event_type: str
    actor: str
    description: str


class IncidentTimelineBuilder:

    def build(self, events) -> List[TimelineEntry]:
        ordered = sorted(events, key=lambda event: event.timestamp)

        return [
            TimelineEntry(
                timestamp=event.timestamp,
                event_id=event.event_id,
                event_type=event.event_type.value,
                actor=event.actor,
                description=self._describe(event),
            )
            for event in ordered
        ]

    @staticmethod
    def _describe(event) -> str:
        return event.payload.get("description", event.event_type.value)
