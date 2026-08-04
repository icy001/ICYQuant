"""
Feature flag platform audit framework.

Provides audit logging for feature flag
operations including creation, updates,
state changes, evaluations, and deletions.
Supports querying audit history and
exporting audit entries for compliance.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .constants import OperatorAction
from .exceptions import FeatureFlagError
from .models import AuditEntry, FeatureEvaluationResult
from .utils import generate_id, generate_trace_id

logger = logging.getLogger(__name__)


class AuditManager:
    """
    Centralized audit logging for feature flag operations.

    Records all feature flag changes and evaluations
    with operator, old/new values, timestamps, and
    trace IDs for compliance and debugging.

    Usage:
        audit = AuditManager()
        audit.record_create(flag=my_flag, operator="admin")
        audit.record_update(flag=updated, old_enabled=True, new_enabled=False)
        entries = audit.query(flag_key="trading.new_risk")
    """

    def __init__(
        self,
        max_entries: int = 10000,
    ) -> None:
        """
        Initialize the audit manager.

        Args:
            max_entries: Maximum audit entries to retain.
        """
        self._entries: List[AuditEntry] = []
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
        self._listeners: List[Callable[[AuditEntry], None]] = []
        self._counters: Dict[str, int] = {
            "create": 0,
            "update": 0,
            "delete": 0,
            "enable": 0,
            "disable": 0,
            "evaluate": 0,
            "rollback": 0,
        }

    async def record_create(
        self,
        flag_key: str = "",
        flag: Any = None,
        operator: str = "system",
        reason: str = "",
        trace_id: str = "",
    ) -> AuditEntry:
        """
        Record a flag creation.

        Args:
            flag_key: Feature flag key.
            flag: Created flag object (optional).
            operator: Who performed the action.
            reason: Reason for the change.
            trace_id: Correlation trace ID.

        Returns:
            The created audit entry.
        """
        key = flag_key or (flag.key if flag else "")
        entry = AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.CREATE,
            flag_key=key,
            operator=operator,
            new_value=self._extract_value(flag),
            reason=reason or "flag_created",
            trace_id=trace_id or generate_trace_id(),
        )

        await self._store_entry(entry)
        self._counters["create"] += 1

        logger.info(
            "AUDIT: CREATE flag=%s operator=%s",
            key, operator,
        )
        return entry

    async def record_update(
        self,
        flag_key: str = "",
        flag: Any = None,
        old_enabled: Optional[bool] = None,
        new_enabled: Optional[bool] = None,
        operator: str = "system",
        reason: str = "",
        trace_id: str = "",
    ) -> AuditEntry:
        """
        Record a flag update.

        Args:
            flag_key: Feature flag key.
            flag: Updated flag object.
            old_enabled: Previous enabled state.
            new_enabled: New enabled state.
            operator: Who performed the action.
            reason: Reason for the change.
            trace_id: Correlation trace ID.

        Returns:
            The created audit entry.
        """
        key = flag_key or (flag.key if flag else "")
        entry = AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.UPDATE,
            flag_key=key,
            operator=operator,
            old_value={"enabled": old_enabled} if old_enabled is not None else None,
            new_value={
                "enabled": new_enabled,
                "description": flag.description if flag else None,
                "flag_type": flag.flag_type.value if flag else None,
            },
            reason=reason or "flag_updated",
            trace_id=trace_id or generate_trace_id(),
        )

        await self._store_entry(entry)
        self._counters["update"] += 1

        logger.info(
            "AUDIT: UPDATE flag=%s operator=%s",
            key, operator,
        )
        return entry

    async def record_delete(
        self,
        flag_key: str = "",
        flag: Any = None,
        operator: str = "system",
        reason: str = "",
        trace_id: str = "",
    ) -> AuditEntry:
        """
        Record a flag deletion.

        Args:
            flag_key: Feature flag key.
            flag: Deleted flag object (for value reference).
            operator: Who performed the action.
            reason: Reason for the change.
            trace_id: Correlation trace ID.

        Returns:
            The created audit entry.
        """
        key = flag_key or (flag.key if flag else "")
        entry = AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.DELETE,
            flag_key=key,
            operator=operator,
            old_value=self._extract_value(flag),
            reason=reason or "flag_deleted",
            trace_id=trace_id or generate_trace_id(),
        )

        await self._store_entry(entry)
        self._counters["delete"] += 1

        logger.info(
            "AUDIT: DELETE flag=%s operator=%s",
            key, operator,
        )
        return entry

    async def record_state_change(
        self,
        flag_key: str,
        old_enabled: bool,
        new_enabled: bool,
        operator: str = "system",
        reason: str = "",
        trace_id: str = "",
    ) -> AuditEntry:
        """
        Record a flag enable/disable state change.

        Args:
            flag_key: Feature flag key.
            old_enabled: Previous state.
            new_enabled: New state.
            operator: Who performed the action.
            reason: Reason for the change.
            trace_id: Correlation trace ID.

        Returns:
            The created audit entry.
        """
        action = (
            OperatorAction.ENABLE
            if new_enabled else OperatorAction.DISABLE
        )

        entry = AuditEntry(
            entry_id=generate_id(),
            action=action,
            flag_key=flag_key,
            operator=operator,
            old_value=old_enabled,
            new_value=new_enabled,
            reason=reason or f"flag_{action.value}d",
            trace_id=trace_id or generate_trace_id(),
        )

        await self._store_entry(entry)
        self._counters[action.value] += 1

        logger.info(
            "AUDIT: %s flag=%s %s->%s operator=%s",
            action.value.upper(), flag_key,
            old_enabled, new_enabled, operator,
        )
        return entry

    async def record_evaluation(
        self,
        flag_key: str,
        result: FeatureEvaluationResult,
        context: Optional[Any] = None,
    ) -> AuditEntry:
        """
        Record a flag evaluation.

        Args:
            flag_key: Feature flag key.
            result: Evaluation result.
            context: Evaluation context.

        Returns:
            The created audit entry.
        """
        entry = AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.EVALUATE,
            flag_key=flag_key,
            operator=context.target_type if context else "anonymous",
            new_value=result.value,
            reason=result.reason,
            trace_id=(
                context.request_id
                if context and hasattr(context, "request_id")
                else ""
            ),
            metadata={
                "result": result.result.value,
                "duration_ms": result.duration_ms,
                "matched_rule_id": result.matched_rule_id,
            },
        )

        self._counters["evaluate"] += 1
        return entry

    async def record_rule_evaluation(
        self,
        flag_key: str,
        rule_id: str,
        matched: bool,
        value: Any = None,
        context: Optional[Any] = None,
        trace: Optional[list] = None,
    ) -> AuditEntry:
        """
        Record a targeting rule evaluation.

        Args:
            flag_key: Feature flag key.
            rule_id: Matched rule ID.
            matched: Whether the rule matched.
            value: Rule value.
            context: Evaluation context.
            trace: Evaluation trace for diagnostics.

        Returns:
            The created audit entry.
        """
        self._counters["evaluate"] += 1

        return AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.EVALUATE,
            flag_key=flag_key,
            operator=(
                context.target_type
                if context and hasattr(context, "target_type")
                else "anonymous"
            ),
            new_value=value,
            reason=f"targeting_rule:{rule_id}:{'matched' if matched else 'not_matched'}",
            trace_id=(
                context.request_id
                if context and hasattr(context, "request_id")
                else generate_trace_id()
            ),
            metadata={
                "rule_id": rule_id,
                "matched": matched,
                "trace": trace or [],
            },
        )

    async def record_rollback(
        self,
        flag_key: str,
        old_value: Any,
        new_value: Any,
        operator: str = "system",
        reason: str = "",
    ) -> AuditEntry:
        """
        Record a flag rollback.

        Args:
            flag_key: Feature flag key.
            old_value: Value before rollback.
            new_value: Restored value.
            operator: Who performed the action.
            reason: Reason for rollback.

        Returns:
            The created audit entry.
        """
        entry = AuditEntry(
            entry_id=generate_id(),
            action=OperatorAction.ROLLBACK,
            flag_key=flag_key,
            operator=operator,
            old_value=old_value,
            new_value=new_value,
            reason=reason or "flag_rollback",
            trace_id=generate_trace_id(),
        )

        await self._store_entry(entry)
        self._counters["rollback"] += 1

        logger.info(
            "AUDIT: ROLLBACK flag=%s operator=%s",
            flag_key, operator,
        )
        return entry

    async def query(
        self,
        flag_key: Optional[str] = None,
        action: Optional[OperatorAction] = None,
        operator: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Query audit entries with optional filters.

        Args:
            flag_key: Filter by flag key.
            action: Filter by action type.
            operator: Filter by operator.
            start_time: Start time for range query.
            end_time: End time for range query.
            limit: Maximum number of entries to return.

        Returns:
            List of matching audit entries.
        """
        async with self._lock:
            entries = list(reversed(self._entries))

        if flag_key:
            entries = [e for e in entries if e.flag_key == flag_key]
        if action:
            entries = [e for e in entries if e.action == action]
        if operator:
            entries = [e for e in entries if e.operator == operator]
        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]
        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        return entries[:limit]

    async def get_entry(
        self,
        entry_id: str,
    ) -> Optional[AuditEntry]:
        """
        Get a specific audit entry by ID.

        Args:
            entry_id: Audit entry ID.

        Returns:
            AuditEntry or None.
        """
        async with self._lock:
            for entry in self._entries:
                if entry.entry_id == entry_id:
                    return entry
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get audit manager statistics."""
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
            "by_action": dict(self._counters),
        }

    def register_listener(
        self,
        listener: Callable[[AuditEntry], None],
    ) -> None:
        """
        Register a listener for audit entries.

        Args:
            listener: Callable invoked with each new entry.
        """
        self._listeners.append(listener)

    def unregister_listener(
        self,
        listener: Callable[[AuditEntry], None],
    ) -> None:
        """
        Unregister an audit listener.

        Args:
            listener: Callable to remove.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def clear(self) -> None:
        """Clear all audit entries."""
        async with self._lock:
            self._entries.clear()
            self._counters = {k: 0 for k in self._counters}

    async def export(
        self,
        format: str = "dict",
    ) -> List[Dict[str, Any]]:
        """
        Export audit entries.

        Args:
            format: Export format ("dict" or "json-serializable").

        Returns:
            List of exported entries.
        """
        async with self._lock:
            return [self._entry_to_dict(e) for e in self._entries]

    async def _store_entry(
        self,
        entry: AuditEntry,
    ) -> None:
        """Store an audit entry with eviction."""
        async with self._lock:
            self._entries.append(entry)

            if len(self._entries) > self._max_entries:
                excess = len(self._entries) - self._max_entries
                self._entries = self._entries[excess:]

        for listener in self._listeners:
            try:
                listener(entry)
            except Exception as e:
                logger.warning(
                    "Audit listener error: %s", e,
                )

    def _extract_value(self, flag: Any) -> Any:
        """Extract a serializable value from a flag."""
        if flag is None:
            return None
        return {
            "key": flag.key,
            "enabled": flag.enabled,
            "description": flag.description,
            "flag_type": flag.flag_type.value if hasattr(flag, "flag_type") else None,
            "default_value": flag.default_value if hasattr(flag, "default_value") else None,
        }

    def _entry_to_dict(
        self,
        entry: AuditEntry,
    ) -> Dict[str, Any]:
        """Convert an audit entry to a dictionary."""
        return {
            "entry_id": entry.entry_id,
            "action": entry.action.value,
            "flag_key": entry.flag_key,
            "operator": entry.operator,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "reason": entry.reason,
            "trace_id": entry.trace_id,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp.isoformat(),
        }