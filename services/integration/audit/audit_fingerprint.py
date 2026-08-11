"""Audit Fingerprint — content-based integrity digest for audit records.

Computes a fingerprint over an entire audit record's events and
metadata, enabling tamper detection at the record level.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .audit_event import AuditEvent
from .audit_record import AuditRecord


def compute_audit_fingerprint(record_id: str, lineage_id: str,
                              events: list[AuditEvent],
                              chain_hash: str,
                              ) -> str:
    """Compute a record-level fingerprint covering all events."""
    material: dict[str, Any] = {
        "record_id": record_id,
        "lineage_id": lineage_id,
        "event_hashes": [e.event_hash for e in events],
        "chain_hash": chain_hash,
        "event_count": len(events),
    }
    serialized = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_event_fingerprint(event: AuditEvent) -> str:
    """Compute a single-event fingerprint."""
    from .audit_event import compute_event_hash

    return compute_event_hash(
        event_id=event.event_id,
        event_type=event.event_type.name,
        lineage_id=event.lineage_id,
        timestamp=event.timestamp,
        actor=event.actor_type.name,
        actor_id=event.actor_id,
        payload=event.payload,
        previous_event_hash=event.previous_event_hash,
    )


@dataclass
class AuditFingerprint:
    """Represents a computed fingerprint for an audit record or event.

    Stores the fingerprint value and the time it was computed.
    Supports verification against a record.
    """

    fingerprint: str = ""
    record_id: str = ""
    lineage_id: str = ""
    computed_at: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    # ── Factory methods ───────────────────────────────────────────

    @classmethod
    def for_record(cls, record: AuditRecord) -> "AuditFingerprint":
        fp = compute_audit_fingerprint(
            record_id=record.record_id,
            lineage_id=record.lineage_id,
            events=record.events,
            chain_hash=record.chain_hash,
        )
        import time as _t
        return cls(
            fingerprint=fp,
            record_id=record.record_id,
            lineage_id=record.lineage_id,
            computed_at=_t.time(),
        )

    @classmethod
    def for_event(cls, event: AuditEvent) -> "AuditFingerprint":
        fp = compute_event_fingerprint(event)
        import time as _t
        return cls(
            fingerprint=fp,
            record_id="",
            lineage_id=event.lineage_id,
            computed_at=_t.time(),
        )

    # ── Verification ──────────────────────────────────────────────

    def verify(self, record: AuditRecord) -> bool:
        """Check whether this fingerprint still matches the record."""
        current = compute_audit_fingerprint(
            record_id=record.record_id,
            lineage_id=record.lineage_id,
            events=record.events,
            chain_hash=record.chain_hash,
        )
        return current == self.fingerprint

    def verify_event(self, event: AuditEvent) -> bool:
        """Check whether an event's fingerprint matches."""
        return compute_event_fingerprint(event) == self.fingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "record_id": self.record_id,
            "lineage_id": self.lineage_id,
            "computed_at": self.computed_at,
        }
