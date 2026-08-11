"""Audit Chain — hash-linked sequence of audit events.

Provides integrity verification by checking that every event's hash
correctly references its predecessor, forming an unbroken chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit_event import AuditEvent, compute_event_hash
from .audit_record import AuditRecord


@dataclass
class AuditChainIntegrityReport:
    """Result of an audit chain integrity check."""

    valid: bool = True
    record_id: str = ""
    lineage_id: str = ""
    events_checked: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


@dataclass
class AuditChain:
    """Manages and verifies a hash-linked audit event chain.

    The chain invariant: for event at position i (i > 0):
        event[i].previous_event_hash == SHA-256(event[i-1])
    """

    _records: dict[str, AuditRecord] = field(default_factory=dict)

    # ── Record management ─────────────────────────────────────────

    def create_record(self, lineage_id: str,
                      record_id: str = "",
                      ) -> AuditRecord:
        """Create and register a new audit record."""
        rid = record_id or (
            f"AREC-{__import__('uuid').uuid4().hex[:12].upper()}"
        )
        record = AuditRecord(record_id=rid, lineage_id=lineage_id)
        self._records[rid] = record
        return record

    def get_record(self, record_id: str) -> AuditRecord | None:
        return self._records.get(record_id)

    def get_record_by_lineage(self, lineage_id: str) -> AuditRecord | None:
        for rec in self._records.values():
            if rec.lineage_id == lineage_id:
                return rec
        return None

    # ── Integrity verification ────────────────────────────────────

    def verify_chain(self, record: AuditRecord,
                     ) -> AuditChainIntegrityReport:
        """Verify the hash-linked chain of events in a record.

        Checks that each event's previous_event_hash matches the
        computed hash of the preceding event.
        """
        report = AuditChainIntegrityReport(
            record_id=record.record_id,
            lineage_id=record.lineage_id,
        )

        if not record.events:
            return report

        for i, event in enumerate(record.events):
            report.events_checked += 1

            # Verify event's own hash
            expected_hash = compute_event_hash(
                event_id=event.event_id,
                event_type=event.event_type.name,
                lineage_id=event.lineage_id,
                timestamp=event.timestamp,
                actor=event.actor_type.name,
                actor_id=event.actor_id,
                payload=event.payload,
                previous_event_hash=event.previous_event_hash,
            )
            if expected_hash != event.event_hash:
                report.add_error(
                    f"Event {event.event_id} (seq={i}): "
                    f"stored hash does not match computed hash"
                )

            # Verify linkage to previous event
            if i > 0:
                prev = record.events[i - 1]
                if event.previous_event_hash != prev.event_hash:
                    report.add_error(
                        f"Event {event.event_id} (seq={i}): "
                        f"previous_event_hash does not match "
                        f"hash of event {prev.event_id} (seq={i-1})"
                    )

            # Verify sequence_number
            if event.sequence_number != i:
                report.add_error(
                    f"Event {event.event_id}: "
                    f"expected seq={i}, got seq={event.sequence_number}"
                )

        # Verify chain_hash at record level
        if record.events and record.chain_hash != record.events[-1].event_hash:
            report.add_error(
                f"Record chain_hash does not match hash of last event"
            )

        return report

    def verify_all(self) -> list[AuditChainIntegrityReport]:
        """Verify chain integrity for all registered records."""
        return [self.verify_chain(rec)
                for rec in self._records.values()]
