"""
IncidentAuditEvent — immutable, tamper-evident audit record.

Key principle (spec section 3): an audit event, once written, must never be
modified in place.  The dataclass is frozen; the hash chain (spec section 7)
makes tampering detectable even outside the process that wrote the events.

    Event N-1 ── hash ──▶ Event N ── previous_hash + event_hash ──▶ Event N+1

``previous_hash`` links to the predecessor, ``event_hash`` covers every
canonical field of this event (including its payload), so mutating, deleting
or reordering any event breaks the chain.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .event_type import IncidentAuditEventType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def calculate_event_hash(
    event_payload: Dict[str, Any],
    previous_hash: Optional[str],
) -> str:
    """SHA-256 over ``{previous_hash, payload}`` (spec section 7).

    ``default=str`` keeps the hash stable for payloads that contain UUIDs or
    datetimes — canonical JSON never has to fail on a value type.
    """
    canonical = json.dumps(
        {
            "previous_hash": previous_hash,
            "payload": event_payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IncidentAuditEvent:
    """A single immutable audit event.

    ``incident_id`` is the string form of the incident identifier
    (``IncidentId.value``, e.g. ``INC-20260812-000001``); this mirrors the
    domain aggregate which does not expose a UUID.
    """

    incident_id: str
    event_type: IncidentAuditEventType
    actor: str

    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=_utcnow)

    correlation_id: Optional[str] = None
    command_id: Optional[UUID] = None
    action_id: Optional[UUID] = None

    payload: Dict[str, Any] = field(default_factory=dict)

    previous_hash: Optional[str] = None
    event_hash: Optional[str] = None


def event_payload(event: IncidentAuditEvent) -> Dict[str, Any]:
    """Canonical, hashable representation of an audit event.

    Shared by the recorder (when signing) and the verifier (when checking), so
    the two can never drift apart.
    """
    return {
        "event_id": str(event.event_id),
        "timestamp": event.timestamp.isoformat(),
        "event_type": event.event_type.value,
        "actor": event.actor,
        "incident_id": event.incident_id,
        "correlation_id": event.correlation_id,
        "command_id": str(event.command_id) if event.command_id else None,
        "action_id": str(event.action_id) if event.action_id else None,
        "payload": event.payload,
    }


def verify_event_chain(events: List[IncidentAuditEvent]) -> bool:
    """Return True when every hash links to its predecessor (spec section 7).

    Detects in-place modification, deletion and reordering: any tampered event
    fails its own hash, any missing or moved event breaks ``previous_hash``.
    """
    expected_previous: Optional[str] = None
    for event in events:
        if event.previous_hash != expected_previous:
            return False
        recomputed = calculate_event_hash(
            event_payload(event),
            event.previous_hash,
        )
        if recomputed != event.event_hash:
            return False
        expected_previous = event.event_hash
    return True
