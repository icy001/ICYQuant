"""HA audit trail for ICYQuant service discovery HA.

Provides ``HAAudit`` for recording a comprehensive audit trail
of HA events including failures, promotions, recoveries, and
rollbacks.  Supports querying by service name and event type.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAAudit:
    """Maintains an audit trail of HA events.

    Records failures, promotions, recoveries, rollbacks, and
    generic audit entries.  Supports filtering by service name
    and event type.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: List[Dict[str, Any]] = []
        self._record_count = 0
        self._failure_count = 0
        self._promotion_count = 0
        self._recovery_count = 0
        self._rollback_count = 0
        self._max_entries = 1000

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _add_entry(self, entry: Dict[str, Any]) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            excess = len(self._entries) - self._max_entries
            del self._entries[:excess]

    # ── Public API ──

    def record(
        self,
        event_type: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None,
        operator: str = "system",
    ) -> None:
        """Record a generic audit event.

        Args:
            event_type: The type of event (e.g., 'config_change',
                'manual_intervention').
            service_name: The affected service.
            details: Optional event details.
            operator: The operator who triggered the event.
        """
        with self._lock:
            self._record_count += 1
            entry: Dict[str, Any] = {
                "event_type": event_type,
                "service_name": service_name,
                "details": dict(details) if details else {},
                "operator": operator,
                "timestamp": self._now_iso(),
                "epoch": time.time(),
            }
            self._add_entry(entry)
        logger.info(
            "Audit record: '%s' for '%s' by '%s'.",
            event_type,
            service_name,
            operator,
        )

    def record_failure(
        self,
        service_name: str,
        failure_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a service failure event.

        Args:
            service_name: The affected service.
            failure_type: Classification of the failure.
            details: Optional failure details.
        """
        with self._lock:
            self._failure_count += 1
            entry: Dict[str, Any] = {
                "event_type": "failure",
                "service_name": service_name,
                "failure_type": failure_type,
                "details": dict(details) if details else {},
                "operator": "system",
                "timestamp": self._now_iso(),
                "epoch": time.time(),
            }
            self._add_entry(entry)
        logger.warning(
            "Audit failure: type='%s' for '%s'.",
            failure_type,
            service_name,
        )

    def record_promotion(
        self,
        service_name: str,
        from_instance: str,
        to_instance: str,
    ) -> None:
        """Record a replica promotion event.

        Args:
            service_name: The affected service.
            from_instance: The demoted instance.
            to_instance: The promoted instance.
        """
        with self._lock:
            self._promotion_count += 1
            entry: Dict[str, Any] = {
                "event_type": "promotion",
                "service_name": service_name,
                "from_instance": from_instance,
                "to_instance": to_instance,
                "details": {
                    "from_instance": from_instance,
                    "to_instance": to_instance,
                },
                "operator": "system",
                "timestamp": self._now_iso(),
                "epoch": time.time(),
            }
            self._add_entry(entry)
        logger.info(
            "Audit promotion: '%s' %s -> %s.",
            service_name,
            from_instance,
            to_instance,
        )

    def record_recovery(
        self,
        service_name: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a recovery event.

        Args:
            service_name: The affected service.
            success: Whether recovery succeeded.
            details: Optional recovery details.
        """
        with self._lock:
            self._recovery_count += 1
            entry: Dict[str, Any] = {
                "event_type": "recovery",
                "service_name": service_name,
                "success": success,
                "details": dict(details) if details else {},
                "operator": "system",
                "timestamp": self._now_iso(),
                "epoch": time.time(),
            }
            self._add_entry(entry)
        if success:
            logger.info(
                "Audit recovery: '%s' succeeded.", service_name
            )
        else:
            logger.warning(
                "Audit recovery: '%s' failed.", service_name
            )

    def record_rollback(
        self,
        service_name: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a rollback event.

        Args:
            service_name: The affected service.
            reason: Reason for the rollback.
            details: Optional rollback details.
        """
        with self._lock:
            self._rollback_count += 1
            entry: Dict[str, Any] = {
                "event_type": "rollback",
                "service_name": service_name,
                "rollback_reason": reason,
                "details": dict(details) if details else {},
                "operator": "system",
                "timestamp": self._now_iso(),
                "epoch": time.time(),
            }
            self._add_entry(entry)
        logger.warning(
            "Audit rollback: '%s' reason='%s'.",
            service_name,
            reason,
        )

    def get_audit_trail(
        self,
        service_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit entries, optionally filtered by service.

        Args:
            service_name: Optional filter by service name.
            limit: Maximum number of entries to return.

        Returns:
            A list of audit entries (most recent first).
        """
        with self._lock:
            entries = list(self._entries)
        if service_name is not None:
            entries = [
                e
                for e in entries
                if e.get("service_name") == service_name
            ]
        entries.sort(key=lambda e: e.get("epoch", 0), reverse=True)
        if limit and limit > 0:
            entries = entries[:limit]
        return entries

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the audit trail."""
        with self._lock:
            event_type_counts: Dict[str, int] = {}
            for entry in self._entries:
                et = entry.get("event_type", "unknown")
                event_type_counts[et] = (
                    event_type_counts.get(et, 0) + 1
                )

            return {
                "record_count": self._record_count,
                "failure_count": self._failure_count,
                "promotion_count": self._promotion_count,
                "recovery_count": self._recovery_count,
                "rollback_count": self._rollback_count,
                "event_type_distribution": event_type_counts,
                "entry_count": len(self._entries),
                "max_entries": self._max_entries,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAAudit(entries={len(self._entries)}, "
                f"failures={self._failure_count}, "
                f"recoveries={self._recovery_count})"
            )