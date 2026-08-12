"""
IncidentAuditService — facade for recording and reading audit events.

The service intentionally knows nothing about storage: it delegates to the
recorder and reads back through the recorder's repository, so the API stays
stable when the store changes (spec section 5).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from .event import IncidentAuditEvent
from .event_type import IncidentAuditEventType


class IncidentAuditService:

    def __init__(self, recorder) -> None:
        self.recorder = recorder

    def record(
        self,
        incident_id: str,
        event_type: IncidentAuditEventType,
        *,
        actor: str,
        payload: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        command_id: Optional[UUID] = None,
        action_id: Optional[UUID] = None,
    ) -> IncidentAuditEvent:
        return self.recorder.record(
            incident_id,
            event_type,
            actor=actor,
            payload=payload,
            correlation_id=correlation_id,
            command_id=command_id,
            action_id=action_id,
        )

    def timeline(self, incident_id: str) -> List[IncidentAuditEvent]:
        """All audit events for an incident, in append order."""
        return self.recorder.repository.get(incident_id)
