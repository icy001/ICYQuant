"""Audit Record — container for a sequence of audit events.

An AuditRecord groups events belonging to a single lineage and
provides the root hash for chain verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit_event import AuditEvent


@dataclass
class AuditRecord:
    """A sequence of hash-linked AuditEvents for one control lineage.

    Each record tracks all events from lineage start to completion.
    The chain_hash is the hash of the last event in the chain,
    serving as the root integrity proof.
    """

    record_id: str = field(
        default_factory=lambda: (
            f"AREC-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    lineage_id: str = ""
    events: list[AuditEvent] = field(default_factory=list)
    created_at: float = field(
        default_factory=lambda: __import__("time").time(),
    )
    chain_hash: str = ""
    is_frozen: bool = False

    # ── Mutators ──────────────────────────────────────────────────

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append a sealed event to the audit record.

        Raises ValueError if the record is frozen or event not sealed.
        """
        if self.is_frozen:
            raise ValueError(
                f"AuditRecord {self.record_id} is frozen — cannot append"
            )
        if not event.event_hash:
            raise ValueError(
                f"Event {event.event_id} must be sealed before appending"
            )

        self.events.append(event)

        # Update chain_hash to the latest event's hash
        self.chain_hash = event.event_hash
        return event

    def append_and_seal(self, event: AuditEvent) -> AuditEvent:
        """Seal an event with appropriate chain linkage, then append."""
        prev_hash = self.events[-1].event_hash if self.events else ""
        seq = len(self.events)
        event.seal(previous_hash=prev_hash, sequence_number=seq)
        return self.append(event)

    def freeze(self) -> None:
        """Mark the record as frozen — no more events allowed."""
        self.is_frozen = True

    # ── Queries ───────────────────────────────────────────────────

    @property
    def event_count(self) -> int:
        return len(self.events)

    def get_event(self, event_id: str) -> AuditEvent | None:
        for e in self.events:
            if e.event_id == event_id:
                return e
        return None

    def get_event_at_sequence(self, seq: int) -> AuditEvent | None:
        for e in self.events:
            if e.sequence_number == seq:
                return e
        return None

    def get_events_by_type(self, event_type_name: str) -> list[AuditEvent]:
        return [e for e in self.events
                if e.event_type.name == event_type_name]

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "lineage_id": self.lineage_id,
            "events": [e.to_dict() for e in self.events],
            "created_at": self.created_at,
            "chain_hash": self.chain_hash,
            "is_frozen": self.is_frozen,
            "event_count": len(self.events),
        }
