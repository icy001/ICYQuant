"""
Secrets audit framework.

Provides comprehensive audit logging for
all secret operations, supporting compliance,
forensics, and security audit requirements.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .constants import AuditAction

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """
    Single audit log entry.

    Attributes:
        entry_id: Unique entry identifier.
        action: Action performed (read, write, etc.).
        key: Secret key involved.
        namespace: Namespace.
        operator: Who performed the action.
        source: Source of the action.
        allowed: Whether access was allowed.
        cache_hit: Whether value came from cache.
        latency_ms: Operation latency in ms.
        trace_id: Trace ID for correlation.
        timestamp: When the action occurred.
        details: Additional context.
    """

    entry_id: str = ""
    action: str = ""
    key: str = ""
    namespace: str = "default"
    operator: str = "system"
    source: str = ""
    allowed: bool = True
    cache_hit: bool = False
    latency_ms: float = 0.0
    trace_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "action": self.action,
            "key": self.key,
            "namespace": self.namespace,
            "operator": self.operator,
            "source": self.source,
            "allowed": self.allowed,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "details": self.details,
        }


class SecretsAudit:
    """
    Secrets audit logger.

    Records all secret operations for
    compliance, forensics, and security
    auditing. Supports both in-memory and
    persistent storage backends.

    Usage:
        audit = SecretsAudit()
        audit.log_access(key="db/password", operator="service1")
        entries = audit.query(action="read", key="db/*")
    """

    def __init__(
        self,
        enabled: bool = True,
        max_entries: int = 50000,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            enabled: Whether audit is enabled.
            max_entries: Maximum entries to keep.
        """
        self._enabled = enabled
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: List[AuditEntry] = []
        self._listeners: List[Callable] = []
        # Statistics
        self._total_actions = 0
        self._actions_by_type: Dict[str, int] = {}

    # ── Logging ──

    def log_access(
        self,
        key: str,
        namespace: str = "default",
        operator: str = "system",
        allowed: bool = True,
        cache_hit: bool = False,
        latency_ms: float = 0.0,
        source: str = "",
        trace_id: str = "",
        **details: Any,
    ) -> AuditEntry:
        """
        Log a secret access event.

        Args:
            key: Secret key.
            namespace: Namespace.
            operator: Who accessed.
            allowed: Whether access was allowed.
            cache_hit: Whether value was cached.
            latency_ms: Access latency.
            source: Access source.
            trace_id: Trace ID for correlation.
            **details: Additional context.

        Returns:
            The created AuditEntry.
        """
        return self._log(
            action=AuditAction.READ.value,
            key=key,
            namespace=namespace,
            operator=operator,
            source=source,
            allowed=allowed,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            trace_id=trace_id,
            details=details,
        )

    def log_change(
        self,
        key: str,
        action: str = "update",
        namespace: str = "default",
        operator: str = "system",
        source: str = "",
        trace_id: str = "",
        **details: Any,
    ) -> AuditEntry:
        """
        Log a secret change event.

        Args:
            key: Secret key.
            action: Change action (create, update, delete, rotate).
            namespace: Namespace.
            operator: Who made the change.
            source: Change source.
            trace_id: Trace ID.
            **details: Additional context.

        Returns:
            The created AuditEntry.
        """
        return self._log(
            action=action,
            key=key,
            namespace=namespace,
            operator=operator,
            source=source,
            allowed=True,
            trace_id=trace_id,
            details=details,
        )

    def log_error(
        self,
        key: str,
        error: str,
        namespace: str = "default",
        operator: str = "system",
        trace_id: str = "",
        **details: Any,
    ) -> AuditEntry:
        """
        Log a secret error event.

        Args:
            key: Secret key.
            error: Error description.
            namespace: Namespace.
            operator: Who encountered the error.
            trace_id: Trace ID.
            **details: Additional context.

        Returns:
            The created AuditEntry.
        """
        return self._log(
            action="error",
            key=key,
            namespace=namespace,
            operator=operator,
            allowed=False,
            trace_id=trace_id,
            details={"error": error, **details},
        )

    def _log(
        self,
        action: str,
        key: str,
        namespace: str = "default",
        operator: str = "system",
        source: str = "",
        allowed: bool = True,
        cache_hit: bool = False,
        latency_ms: float = 0.0,
        trace_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Internal log method."""
        if not self._enabled:
            return AuditEntry()

        with self._lock:
            entry = AuditEntry(
                entry_id=str(uuid.uuid4()),
                action=action,
                key=key,
                namespace=namespace,
                operator=operator,
                source=source,
                allowed=allowed,
                cache_hit=cache_hit,
                latency_ms=latency_ms,
                trace_id=trace_id,
                timestamp=datetime.utcnow(),
                details=details or {},
            )

            self._entries.append(entry)

            # Trim if over limit
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

            # Update stats
            self._total_actions += 1
            self._actions_by_type[action] = self._actions_by_type.get(action, 0) + 1

            # Notify listeners
            self._notify_listeners(entry)

            return entry

    # ── Query ──

    def query(
        self,
        action: Optional[str] = None,
        key_pattern: Optional[str] = None,
        namespace: Optional[str] = None,
        operator: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Query audit entries.

        Args:
            action: Filter by action type.
            key_pattern: Filter by key pattern (fnmatch).
            namespace: Filter by namespace.
            operator: Filter by operator.
            limit: Max entries to return.

        Returns:
            List of matching AuditEntry.
        """
        import fnmatch

        with self._lock:
            results = list(reversed(self._entries))  # Most recent first

            if action:
                results = [e for e in results if e.action == action]
            if key_pattern:
                results = [e for e in results if fnmatch.fnmatch(e.key, key_pattern)]
            if namespace:
                results = [e for e in results if e.namespace == namespace]
            if operator:
                results = [e for e in results if e.operator == operator]

            return results[:limit]

    def get_recent(
        self,
        limit: int = 50,
    ) -> List[AuditEntry]:
        """Get most recent audit entries."""
        with self._lock:
            return list(reversed(self._entries[-limit:]))

    def get_for_key(
        self,
        key: str,
        limit: int = 50,
    ) -> List[AuditEntry]:
        """Get audit entries for a specific key."""
        return self.query(key_pattern=key, limit=limit)

    # ── Listeners ──

    def add_listener(
        self,
        listener: Callable,
    ) -> None:
        """
        Add an audit event listener.

        Args:
            listener: Callable(AuditEntry) to invoke.
        """
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable,
    ) -> None:
        """Remove an audit event listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(self, entry: AuditEntry) -> None:
        """Notify all listeners of a new entry."""
        for listener in self._listeners:
            try:
                listener(entry)
            except Exception:
                logger.warning("Audit listener error")

    # ── Management ──

    @property
    def enabled(self) -> bool:
        """Check if audit is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable/disable audit."""
        self._enabled = value

    def clear(self) -> None:
        """Clear all audit entries."""
        with self._lock:
            self._entries.clear()
            self._total_actions = 0
            self._actions_by_type.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "total_entries": len(self._entries),
                "total_actions": self._total_actions,
                "actions_by_type": dict(self._actions_by_type),
                "listeners": len(self._listeners),
                "max_entries": self._max_entries,
            }
