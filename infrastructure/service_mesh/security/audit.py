"""Security audit for ICYQuant Service Mesh.

Provides ``SecurityAudit`` for recording security events including
authentication, authorization, certificate lifecycle, rotation,
policy changes, and security incidents for compliance and tracing.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType:
    """Audit event types."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CERTIFICATE_ISSUE = "certificate_issue"
    CERTIFICATE_REVOKE = "certificate_revoke"
    CERTIFICATE_ROTATE = "certificate_rotate"
    CERTIFICATE_EXPIRE = "certificate_expire"
    POLICY_CHANGE = "policy_change"
    MTLS_HANDSHAKE = "mtls_handshake"
    IDENTITY_CREATE = "identity_create"
    IDENTITY_REVOKE = "identity_revoke"
    SECURITY_INCIDENT = "security_incident"
    KEY_ROTATION = "key_rotation"


class AuditSeverity:
    """Audit severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditRecord:
    """A single audit record."""

    def __init__(
        self,
        event_type: str,
        actor: str = "",
        resource: str = "",
        action: str = "",
        severity: str = AuditSeverity.INFO,
        details: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
    ) -> None:
        self.event_type = event_type
        self.actor = actor
        self.resource = resource
        self.action = action
        self.severity = severity
        self.details = details or {}
        self.outcome = outcome
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor": self.actor,
            "resource": self.resource,
            "action": self.action,
            "severity": self.severity,
            "details": self.details,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
        }


class SecurityAudit:
    """Security audit logger."""

    def __init__(self, max_records: int = 10000) -> None:
        self._lock = threading.RLock()
        self._records: List[Dict[str, Any]] = []
        self._max_records = max_records
        self._record_count = 0
        self._listeners: List = []

    def record(
        self,
        event_type: str,
        actor: str = "",
        resource: str = "",
        action: str = "",
        severity: str = AuditSeverity.INFO,
        details: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
    ) -> Dict[str, Any]:
        """Record a security audit event."""
        record = AuditRecord(
            event_type=event_type,
            actor=actor,
            resource=resource,
            action=action,
            severity=severity,
            details=details,
            outcome=outcome,
        )
        record_dict = record.to_dict()

        with self._lock:
            self._record_count += 1
            record_dict["seq"] = self._record_count
            self._records.append(record_dict)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

        self._notify_listeners(record_dict)
        return record_dict

    def record_authentication(self, principal: str, success: bool, method: str = "certificate") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.AUTHENTICATION,
            actor=principal,
            action=method,
            outcome="success" if success else "failure",
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        )

    def record_authorization(self, principal: str, resource: str, allowed: bool, policy_id: str = "") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.AUTHORIZATION,
            actor=principal,
            resource=resource,
            outcome="allowed" if allowed else "denied",
            severity=AuditSeverity.INFO if allowed else AuditSeverity.WARNING,
            details={"policy_id": policy_id},
        )

    def record_certificate_issue(self, cert_id: str, principal: str, ca_id: str = "") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.CERTIFICATE_ISSUE,
            actor=principal,
            resource=cert_id,
            details={"ca_id": ca_id},
        )

    def record_certificate_revoke(self, cert_id: str, reason: str = "") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.CERTIFICATE_REVOKE,
            resource=cert_id,
            action="revoke",
            severity=AuditSeverity.WARNING,
            details={"reason": reason},
        )

    def record_certificate_rotate(self, cert_id: str, old_cert_id: str = "") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.CERTIFICATE_ROTATE,
            resource=cert_id,
            action="rotate",
            details={"old_cert_id": old_cert_id},
        )

    def record_policy_change(self, policy_id: str, change: str, actor: str = "system") -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.POLICY_CHANGE,
            actor=actor,
            resource=policy_id,
            action=change,
            severity=AuditSeverity.WARNING,
        )

    def record_security_incident(self, description: str, severity: str = AuditSeverity.CRITICAL, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.record(
            event_type=AuditEventType.SECURITY_INCIDENT,
            action="incident",
            severity=severity,
            details=details or {"description": description},
        )

    def get_records(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._records)
        if event_type:
            records = [r for r in records if r["event_type"] == event_type]
        if severity:
            records = [r for r in records if r["severity"] == severity]
        return records[-limit:]

    def subscribe(self, listener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def _notify_listeners(self, record: Dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(record)
            except Exception as exc:
                logger.warning("Audit listener failed: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "record_count": self._record_count,
                "stored_records": len(self._records),
                "listener_count": len(self._listeners),
            }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._record_count = 0
