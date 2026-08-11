"""Audit Query — institutional audit query interface.

Answers questions like:
- "Why did ORDER-001 execute?"
- "What events happened for LINEAGE-001?"
- "Show the full decision audit chain for a trade."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit_event import AuditEvent, EventType
from .audit_record import AuditRecord
from .audit_chain import AuditChain


@dataclass
class AuditQuery:
    """Query interface for audit records and events.

    Operates over AuditChain for chain-level queries and individual
    AuditRecords for event-level queries.
    """

    _chain: AuditChain = field(default_factory=AuditChain)

    # ── Registration ──────────────────────────────────────────────

    def register(self, record: AuditRecord) -> None:
        self._chain._records[record.record_id] = record

    # ── Lineage queries ───────────────────────────────────────────

    def get_lineage_events(self, lineage_id: str) -> dict[str, Any]:
        """Return all events for a lineage."""
        for rec in self._chain._records.values():
            if rec.lineage_id == lineage_id:
                return {
                    "lineage_id": lineage_id,
                    "record_id": rec.record_id,
                    "events": [e.to_dict() for e in rec.events],
                    "event_count": len(rec.events),
                    "chain_hash": rec.chain_hash,
                }
        return {"lineage_id": lineage_id, "events": []}

    # ── Event queries ─────────────────────────────────────────────

    def get_events_by_type(self, lineage_id: str,
                           event_type: EventType) -> list[dict[str, Any]]:
        """Return all events of a given type for a lineage."""
        for rec in self._chain._records.values():
            if rec.lineage_id == lineage_id:
                return [
                    e.to_dict() for e in rec.events
                    if e.event_type == event_type
                ]
        return []

    def get_control_events(self, lineage_id: str) -> list[dict[str, Any]]:
        """Return control-layer events (Risk/Gov/Auth/Approval)."""
        for rec in self._chain._records.values():
            if rec.lineage_id == lineage_id:
                return [
                    e.to_dict() for e in rec.events
                    if e.is_control_event
                ]
        return []

    def get_execution_events(self, lineage_id: str) -> list[dict[str, Any]]:
        """Return execution-layer events (Order/Execution/Trade)."""
        for rec in self._chain._records.values():
            if rec.lineage_id == lineage_id:
                return [
                    e.to_dict() for e in rec.events
                    if e.is_execution_event
                ]
        return []

    # ── Decision audit ────────────────────────────────────────────

    def get_decision_audit(self, lineage_id: str) -> dict[str, Any]:
        """Return the complete decision audit for a lineage.

        This is the "explainable execution" output — why was this
        order allowed and how did it execute?
        """
        events_data = self.get_lineage_events(lineage_id)
        if not events_data.get("events"):
            return {"lineage_id": lineage_id, "audit": []}

        # Build a human-readable summary
        summary: list[dict[str, Any]] = []
        for e in events_data["events"]:
            entry: dict[str, Any] = {
                "sequence": e.get("sequence_number", 0),
                "event_type": e.get("event_type", ""),
                "timestamp": e.get("timestamp", 0),
                "actor": e.get("actor_type", "UNKNOWN"),
                "actor_id": e.get("actor_id", ""),
                "payload": e.get("payload", {}),
                "event_hash": e.get("event_hash", "")[:16] + "...",
            }
            summary.append(entry)

        return {
            "lineage_id": lineage_id,
            "record_id": events_data.get("record_id", ""),
            "chain_hash": events_data.get("chain_hash", ""),
            "audit": sorted(summary, key=lambda x: x["sequence"]),
        }

    # ── History queries ───────────────────────────────────────────

    def get_record_history(self, record_id: str) -> dict[str, Any]:
        """Return the full history for a record."""
        rec = self._chain.get_record(record_id)
        if rec is None:
            return {"record_id": record_id, "events": []}
        return rec.to_dict()
