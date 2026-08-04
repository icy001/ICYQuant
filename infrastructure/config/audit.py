"""
Configuration audit trail.

Records comprehensive audit information for all
configuration changes, providing:
- Who made the change
- When it was made
- What changed
- Old and new values
- Source of the change
- Reason for the change

Essential for:
- Compliance verification
- Risk management
- Operational audit
- Configuration forensics
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class AuditEntry:
    """
    A single audit trail entry.

    Attributes:
        entry_id: Unique audit entry ID.
        timestamp: When the change was recorded.
        event_type: Type of event (create, update, delete, rollback).
        operator: Who performed the action.
        target: What was changed (key or section).
        old_value: Previous value.
        new_value: New value.
        source: Source of the change.
        reason: Reason for the change.
        transaction_id: Related transaction ID.
        checksum: Checksum of the full config after change.
        metadata: Additional context metadata.
    """

    EVENT_CREATE = "create"
    EVENT_UPDATE = "update"
    EVENT_DELETE = "delete"
    EVENT_ROLLBACK = "rollback"
    EVENT_RELOAD = "reload"
    EVENT_IMPORT = "import"
    EVENT_EXPORT = "export"

    def __init__(
        self,
        entry_id: str,
        event_type: str,
        operator: str,
        target: str,
        old_value: Any = None,
        new_value: Any = None,
        source: str = "system",
        reason: str = "",
        transaction_id: Optional[str] = None,
        checksum: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.entry_id = entry_id
        self.timestamp = datetime.utcnow()
        self.event_type = event_type
        self.operator = operator
        self.target = target
        self.old_value = old_value
        self.new_value = new_value
        self.source = source
        self.reason = reason
        self.transaction_id = transaction_id
        self.checksum = checksum
        self.metadata = metadata or {}

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "operator": self.operator,
            "target": self.target,
            "old_value": self._serialize(self.old_value),
            "new_value": self._serialize(self.new_value),
            "source": self.source,
            "reason": self.reason,
            "transaction_id": self.transaction_id,
            "checksum": self.checksum,
            "metadata": self._serialize(self.metadata),
        }

    @staticmethod
    def _serialize(
        value: Any,
    ) -> Any:
        """Serialize value for JSON."""
        try:
            json.dumps(value, default=str)
            return copy.deepcopy(value)
        except (TypeError, ValueError):
            return str(value)

    def get_change_description(
        self,
    ) -> str:
        """Get a human-readable description of the change."""
        if self.event_type == self.EVENT_CREATE:
            return f"Created '{self.target}' = {self._value_str(self.new_value)}"
        elif self.event_type == self.EVENT_UPDATE:
            return (
                f"Updated '{self.target}': "
                f"{self._value_str(self.old_value)} → {self._value_str(self.new_value)}"
            )
        elif self.event_type == self.EVENT_DELETE:
            return f"Deleted '{self.target}' (was {self._value_str(self.old_value)})"
        elif self.event_type == self.EVENT_ROLLBACK:
            return f"Rollback to '{self.target}': {self.reason}"
        elif self.event_type == self.EVENT_RELOAD:
            return f"Reload from {self.source}"
        else:
            return f"{self.event_type}: {self.target}"

    @staticmethod
    def _value_str(
        value: Any,
    ) -> str:
        """Convert value to string for display."""
        if value is None:
            return "null"
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True, default=str)
        return str(value)


class ConfigurationAudit:
    """
    Configuration audit trail manager.

    Records and queries all configuration changes
    for compliance and operational purposes.

    Usage:
        audit = ConfigurationAudit()

        # Record a change
        audit.record(
            event_type=AuditEntry.EVENT_UPDATE,
            operator="admin",
            target="server.port",
            old_value=8080,
            new_value=9090,
            source="file",
            reason="port change",
        )

        # Query audit trail
        entries = audit.query(
            operator="admin",
            event_type=AuditEntry.EVENT_UPDATE,
            limit=50,
        )
    """

    def __init__(
        self,
        max_entries: int = 10000,
    ) -> None:
        """
        Initialize audit trail.

        Args:
            max_entries: Maximum audit entries to retain.
        """
        self._entries: List[AuditEntry] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._counter = 0

    def record(
        self,
        event_type: str,
        operator: str = "system",
        target: str = "",
        old_value: Any = None,
        new_value: Any = None,
        source: str = "system",
        reason: str = "",
        transaction_id: Optional[str] = None,
        config_checksum: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Record an audit entry.

        Args:
            event_type: Event type (create, update, delete, etc.).
            operator: Who performed the action.
            target: What was changed.
            old_value: Previous value.
            new_value: New value.
            source: Source of the change.
            reason: Reason for the change.
            transaction_id: Related transaction ID.
            config_checksum: Full config checksum.
            metadata: Additional context.

        Returns:
            AuditEntry.
        """
        with self._lock:
            self._counter += 1
            entry_id = f"audit_{self._counter:010d}"

        entry = AuditEntry(
            entry_id=entry_id,
            event_type=event_type,
            operator=operator,
            target=target,
            old_value=old_value,
            new_value=new_value,
            source=source,
            reason=reason,
            transaction_id=transaction_id,
            checksum=config_checksum,
            metadata=metadata,
        )

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries.pop(0)

        return entry

    def record_batch(
        self,
        event_type: str,
        operator: str,
        changes: Dict[str, Any],
        old_values: Dict[str, Any],
        source: str = "system",
        reason: str = "",
        transaction_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        """
        Record a batch of changes as individual entries.

        Args:
            event_type: Event type.
            operator: Who performed the action.
            changes: Dict of key → new value.
            old_values: Dict of key → old value.
            source: Source of changes.
            reason: Reason for changes.
            transaction_id: Related transaction ID.

        Returns:
            List of AuditEntry objects.
        """
        entries: List[AuditEntry] = []
        for key, new_val in changes.items():
            old_val = old_values.get(key)
            entry = self.record(
                event_type=event_type,
                operator=operator,
                target=key,
                old_value=old_val,
                new_value=new_val,
                source=source,
                reason=reason,
                transaction_id=transaction_id,
            )
            entries.append(entry)
        return entries

    def query(
        self,
        operator: Optional[str] = None,
        event_type: Optional[str] = None,
        target: Optional[str] = None,
        source: Optional[str] = None,
        transaction_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit trail with filters.

        Args:
            operator: Filter by operator.
            event_type: Filter by event type.
            target: Filter by target key.
            source: Filter by source.
            transaction_id: Filter by transaction ID.
            start_time: Start time filter.
            end_time: End time filter.
            limit: Max results.

        Returns:
            List of matching audit entries.
        """
        with self._lock:
            entries = list(self._entries)

        # Apply filters
        if operator:
            entries = [e for e in entries if e.operator == operator]
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if target:
            entries = [e for e in entries if e.target == target]
        if source:
            entries = [e for e in entries if e.source == source]
        if transaction_id:
            entries = [e for e in entries if e.transaction_id == transaction_id]
        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]
        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return [e.to_dict() for e in entries[:limit]]

    def get_entry(
        self,
        entry_id: str,
    ) -> Optional[AuditEntry]:
        """Get a specific audit entry by ID."""
        with self._lock:
            for entry in reversed(self._entries):
                if entry.entry_id == entry_id:
                    return entry
        return None

    def export(
        self,
        format: str = "json",
        **filters: Any,
    ) -> str:
        """
        Export audit trail.

        Args:
            format: Export format ('json' or 'csv').
            **filters: Query filters.

        Returns:
            Export string.
        """
        entries = self.query(**filters)

        if format == "json":
            return json.dumps(entries, indent=2, default=str)
        elif format == "csv":
            if not entries:
                return ""
            headers = list(entries[0].keys())
            lines = [",".join(headers)]
            for entry in entries:
                values = [
                    str(entry.get(h, "")).replace(",", " ")
                    for h in headers
                ]
                lines.append(",".join(values))
            return "\n".join(lines)
        else:
            return json.dumps(entries, indent=2, default=str)

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get audit trail statistics."""
        with self._lock:
            if not self._entries:
                return {"total_entries": 0}

            operators = set(e.operator for e in self._entries)
            event_types = set(e.event_type for e in self._entries)
            sources = set(e.source for e in self._entries)

            return {
                "total_entries": len(self._entries),
                "operators": sorted(operators),
                "event_types": sorted(event_types),
                "sources": sorted(sources),
                "first_entry": self._entries[0].timestamp.isoformat(),
                "last_entry": self._entries[-1].timestamp.isoformat(),
            }
