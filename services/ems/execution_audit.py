"""Execution Audit — Immutable audit trail for execution operations.

Records all execution events in an append-only audit log for compliance,
debugging, and post-trade analysis.

Audit Trail::

    Execution Event → Audit Log → Persist → Query → Report

Usage::

    audit = ExecutionAudit()
    await audit.record_event(event)
    await audit.record_transition(parent_order_id, "PENDING", "ACTIVE")
    trail = await audit.get_trail(parent_order_id)
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single immutable audit log entry.

    Attributes:
        entry_id: Unique entry identifier
        parent_order_id: Parent order identifier
        child_order_id: Optional child order identifier
        event_type: Type of audited event
        details: Event details
        timestamp: Event timestamp
        actor: Actor/system that triggered the event
        sequence: Monotonically increasing sequence number
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_order_id: str = ""
    child_order_id: Optional[str] = None
    event_type: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "parent_order_id": self.parent_order_id,
            "child_order_id": self.child_order_id,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "sequence": self.sequence,
        }


class ExecutionAudit:
    """Immutable execution audit trail.

    Records all execution events in an append-only log for
    compliance, debugging, and post-trade analysis.

    Attributes:
        _entries: All audit entries
        _by_parent: Entries indexed by parent order
        _sequence: Global sequence counter
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._by_parent: dict[str, list[AuditEntry]] = defaultdict(list)
        self._sequence: int = 0

    # ── Recording ──────────────────────────────────────────────────

    async def record_event(
        self,
        parent_order_id: str,
        event_type: str,
        details: Optional[dict[str, Any]] = None,
        child_order_id: Optional[str] = None,
        actor: str = "system",
    ) -> AuditEntry:
        """Record an execution event in the audit trail.

        Args:
            parent_order_id: Parent order identifier
            event_type: Type of event
            details: Event details
            child_order_id: Optional child order ID
            actor: Actor that triggered the event

        Returns:
            Created AuditEntry
        """
        self._sequence += 1

        entry = AuditEntry(
            parent_order_id=parent_order_id,
            child_order_id=child_order_id,
            event_type=event_type,
            details=details or {},
            actor=actor,
            sequence=self._sequence,
        )

        self._entries.append(entry)
        self._by_parent[parent_order_id].append(entry)

        logger.debug(
            "Audit: %s %s parent=%s seq=%d",
            event_type,
            parent_order_id,
            child_order_id or "",
            self._sequence,
        )
        return entry

    async def record_transition(
        self,
        parent_order_id: str,
        from_status: str,
        to_status: str,
        actor: str = "system",
    ) -> AuditEntry:
        """Record a status transition.

        Args:
            parent_order_id: Parent order identifier
            from_status: Previous status
            to_status: New status
            actor: Actor that triggered the transition

        Returns:
            Created AuditEntry
        """
        return await self.record_event(
            parent_order_id=parent_order_id,
            event_type="STATUS_TRANSITION",
            details={
                "from_status": from_status,
                "to_status": to_status,
            },
            actor=actor,
        )

    async def record_child_created(
        self,
        parent_order_id: str,
        child_order_id: str,
        quantity: float,
        price: float,
    ) -> AuditEntry:
        """Record child order creation.

        Args:
            parent_order_id: Parent order identifier
            child_order_id: Child order identifier
            quantity: Order quantity
            price: Order price

        Returns:
            Created AuditEntry
        """
        return await self.record_event(
            parent_order_id=parent_order_id,
            child_order_id=child_order_id,
            event_type="CHILD_ORDER_CREATED",
            details={"quantity": quantity, "price": price},
        )

    async def record_fill(
        self,
        parent_order_id: str,
        child_order_id: str,
        fill_qty: float,
        fill_price: float,
    ) -> AuditEntry:
        """Record a fill event.

        Args:
            parent_order_id: Parent order identifier
            child_order_id: Child order identifier
            fill_qty: Fill quantity
            fill_price: Fill price

        Returns:
            Created AuditEntry
        """
        return await self.record_event(
            parent_order_id=parent_order_id,
            child_order_id=child_order_id,
            event_type="FILL",
            details={
                "fill_quantity": fill_qty,
                "fill_price": fill_price,
            },
        )

    async def record_algorithm_switch(
        self,
        parent_order_id: str,
        from_strategy: str,
        to_strategy: str,
    ) -> AuditEntry:
        """Record an algorithm strategy switch.

        Args:
            parent_order_id: Parent order identifier
            from_strategy: Previous strategy
            to_strategy: New strategy

        Returns:
            Created AuditEntry
        """
        return await self.record_event(
            parent_order_id=parent_order_id,
            event_type="ALGORITHM_SWITCH",
            details={
                "from_strategy": from_strategy,
                "to_strategy": to_strategy,
            },
        )

    async def record_error(
        self,
        parent_order_id: str,
        error_message: str,
        error_type: str = "UNKNOWN",
    ) -> AuditEntry:
        """Record an error event.

        Args:
            parent_order_id: Parent order identifier
            error_message: Error description
            error_type: Error classification

        Returns:
            Created AuditEntry
        """
        return await self.record_event(
            parent_order_id=parent_order_id,
            event_type="ERROR",
            details={
                "error_type": error_type,
                "error_message": error_message,
            },
        )

    # ── Query API ──────────────────────────────────────────────────

    async def get_trail(self, parent_order_id: str) -> list[AuditEntry]:
        """Get the full audit trail for a parent order.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            List of audit entries in chronological order
        """
        entries = self._by_parent.get(parent_order_id, [])
        return sorted(entries, key=lambda e: e.sequence)

    async def get_recent_entries(self, limit: int = 100) -> list[AuditEntry]:
        """Get the most recent audit entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of recent audit entries
        """
        return self._entries[-limit:]

    async def get_entries_by_type(self, event_type: str) -> list[AuditEntry]:
        """Get all entries of a specific event type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching audit entries
        """
        return [e for e in self._entries if e.event_type == event_type]

    async def get_entry_count(self) -> int:
        """Get total audit entry count.

        Returns:
            Number of audit entries
        """
        return len(self._entries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize audit state."""
        return {
            "total_entries": len(self._entries),
            "parents_audited": len(self._by_parent),
            "sequence": self._sequence,
        }
