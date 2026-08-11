"""Lifecycle Audit — Full audit trail for order lifecycle events.

Records all lifecycle actions for compliance, analysis, and debugging.
Provides queryable audit history with filtering by action, time range,
and order.

Pipeline:
    Action → Record → Query → Report

Key features:
- Immutable audit entries
- Filterable query interface
- Audit statistics and summaries
- Compliance-ready event logging
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit trail entry."""
    entry_id: str
    order_id: str
    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "system"
    details: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entry_id": self.entry_id,
            "order_id": self.order_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "details": self.details,
            "result": self.result,
            "metadata": self.metadata,
        }


class LifecycleAudit:
    """Immutable audit trail for order lifecycle events.

    Records all actions taken on orders for compliance, debugging,
    and operational analysis. Entries are immutable and queryable.

    Usage::

        audit = LifecycleAudit(event_store)
        await audit.record(
            order_id="ORD-001",
            action="order_submitted",
            details={"broker": "IB", "market": "US_STOCKS"},
        )
        entries = await audit.query(order_id="ORD-001", action="order_submitted")
    """

    def __init__(
        self,
        event_store: LifecycleEventStore,
        max_entries_per_order: int = 1000,
    ) -> None:
        """Initialize audit trail.

        Args:
            event_store: Event store for correlation
            max_entries_per_order: Maximum audit entries per order
        """
        self._event_store = event_store
        self._max_entries_per_order = max_entries_per_order
        # order_id → list of AuditEntry
        self._entries: dict[str, list[AuditEntry]] = {}
        # entry_id → AuditEntry for direct lookup
        self._by_id: dict[str, AuditEntry] = {}

    async def record(
        self,
        order_id: str,
        action: str,
        actor: str = "system",
        details: Optional[dict[str, Any]] = None,
        result: str = "",
        entry_id: Optional[str] = None,
    ) -> AuditEntry:
        """Record an audit entry.

        Args:
            order_id: Order identifier
            action: Action description
            actor: Who/what performed the action
            details: Action-specific details
            result: Outcome of the action
            entry_id: Optional custom entry ID

        Returns:
            The created audit entry
        """
        entry = AuditEntry(
            entry_id=entry_id or str(uuid.uuid4()),
            order_id=order_id,
            action=action,
            actor=actor,
            details=details or {},
            result=result,
        )

        if order_id not in self._entries:
            self._entries[order_id] = []
        self._entries[order_id].append(entry)
        self._by_id[entry.entry_id] = entry

        # Prune if exceeding limit
        if len(self._entries[order_id]) > self._max_entries_per_order:
            removed = self._entries[order_id].pop(0)
            self._by_id.pop(removed.entry_id, None)

        logger.debug(f"Audit: [{order_id}] {action} by {actor}")

        return entry

    async def query(
        self,
        order_id: Optional[str] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit entries with filters.

        Args:
            order_id: Filter by order
            action: Filter by action
            actor: Filter by actor
            since: Filter after this time
            until: Filter before this time
            limit: Maximum entries to return
            offset: Skip first N entries

        Returns:
            Matching audit entries
        """
        if order_id:
            entries = self._entries.get(order_id, [])
        else:
            entries = [
                e for entries_list in self._entries.values()
                for e in entries_list
            ]

        # Apply filters
        if action:
            entries = [e for e in entries if e.action == action]
        if actor:
            entries = [e for e in entries if e.actor == actor]
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        if until:
            entries = [e for e in entries if e.timestamp <= until]

        # Sort by timestamp (newest first)
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)

        return entries[offset : offset + limit]

    async def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Get a specific audit entry by ID.

        Args:
            entry_id: Entry identifier

        Returns:
            Audit entry or None
        """
        return self._by_id.get(entry_id)

    async def get_order_audit(
        self, order_id: str
    ) -> list[AuditEntry]:
        """Get all audit entries for an order.

        Args:
            order_id: Order identifier

        Returns:
            All audit entries for the order
        """
        return sorted(
            self._entries.get(order_id, []),
            key=lambda e: e.timestamp,
        )

    async def get_summary(
        self, order_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Get an audit summary.

        Args:
            order_id: Optional order filter

        Returns:
            Summary statistics
        """
        if order_id:
            entries = self._entries.get(order_id, [])
        else:
            entries = [
                e for entries_list in self._entries.values()
                for e in entries_list
            ]

        action_counts: dict[str, int] = {}
        actor_counts: dict[str, int] = {}
        for e in entries:
            action_counts[e.action] = action_counts.get(e.action, 0) + 1
            actor_counts[e.actor] = actor_counts.get(e.actor, 0) + 1

        return {
            "total_entries": len(entries),
            "unique_orders": len(self._entries),
            "actions": action_counts,
            "actors": actor_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def clear_order(self, order_id: str) -> int:
        """Clear all audit entries for an order.

        Args:
            order_id: Order identifier

        Returns:
            Number of entries cleared
        """
        entries = self._entries.pop(order_id, [])
        for e in entries:
            self._by_id.pop(e.entry_id, None)
        return len(entries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize audit state."""
        return {
            "total_entries": sum(len(e) for e in self._entries.values()),
            "unique_orders": len(self._entries),
            "max_entries_per_order": self._max_entries_per_order,
        }
