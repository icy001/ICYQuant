"""
IncidentAuditRecorder — signs and appends chained audit events.

Each event is linked to the previous hash of the same incident, producing the
hash chain that proves no event was deleted or modified in between
(spec section 7).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional
from uuid import UUID

from .event import (
    IncidentAuditEvent,
    calculate_event_hash,
    event_payload,
)
from .event_type import IncidentAuditEventType


class IncidentAuditRecorder:

    def __init__(self, repository) -> None:
        self.repository = repository

    def record(
        self,
        incident_id: str,
        event_type: IncidentAuditEventType,
        *,
        actor: str,
        correlation_id: Optional[str] = None,
        command_id: Optional[UUID] = None,
        action_id: Optional[UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> IncidentAuditEvent:
        """Append a signed event to the incident's audit chain.

        The previous event's hash is read from the repository, so events are
        chained in append order regardless of wall-clock timestamp skew.
        """
        previous = self.repository.get(incident_id)
        previous_hash = previous[-1].event_hash if previous else None

        event = IncidentAuditEvent(
            incident_id=incident_id,
            event_type=event_type,
            actor=actor,
            correlation_id=correlation_id,
            command_id=command_id,
            action_id=action_id,
            payload=payload or {},
            previous_hash=previous_hash,
        )

        signed = replace(
            event,
            event_hash=calculate_event_hash(
                event_payload(event),
                previous_hash,
            ),
        )

        self.repository.append(signed)
        return signed
