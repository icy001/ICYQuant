"""
ICYQuant Audit Center

Immutable audit logging for compliance and regulatory requirements.
Records all critical actions: login, trade, risk approval, policy change,
deployment, AI decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import hashlib
import json

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    TRADE_EXECUTE = "trade_execute"
    TRADE_CANCEL = "trade_cancel"
    RISK_APPROVE = "risk_approve"
    RISK_REJECT = "risk_reject"
    POLICY_CREATE = "policy_create"
    POLICY_UPDATE = "policy_update"
    POLICY_DELETE = "policy_delete"
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    AI_DECISION = "ai_decision"
    PERMISSION_CHANGE = "permission_change"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    COMPLIANCE_CHECK = "compliance_check"
    KEY_ROTATION = "key_rotation"
    INCIDENT = "incident"
    ADMIN_ACTION = "admin_action"


class AuditSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: AuditAction = AuditAction.LOGIN
    actor: str = ""
    target: str = ""
    severity: AuditSeverity = AuditSeverity.INFO
    details: Dict = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    ip_address: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    hash_value: str = ""
    previous_hash: str = ""

    def compute_hash(self) -> str:
        data = json.dumps({
            "id": self.id,
            "action": self.action.value,
            "actor": self.actor,
            "target": self.target,
            "severity": self.severity.value,
            "details": self.details,
            "traceId": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "previousHash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def finalize(self, previous_hash: str = ""):
        self.previous_hash = previous_hash
        self.hash_value = self.compute_hash()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "action": self.action.value,
            "actor": self.actor,
            "target": self.target,
            "severity": self.severity.value,
            "details": self.details,
            "traceId": self.trace_id,
            "sessionId": self.session_id,
            "ipAddress": self.ip_address,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.hash_value,
        }


class AuditCenter:
    """
    Immutable audit logging center.

    Provides cryptographically chained, tamper-evident audit logs
    for all critical platform actions. Supports filtering, export,
    and integration with compliance requirements.
    """

    def __init__(self, retention_days: int = 2555):
        self._entries: List[AuditEntry] = []
        self._retention_days = retention_days
        self._last_hash = ""
        self._action_counts: Dict[str, int] = {}
        self._severity_counts: Dict[str, int] = {}
        self._actor_counts: Dict[str, int] = {}

    def log(
        self,
        action: AuditAction,
        actor: str,
        target: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        details: Optional[Dict] = None,
        trace_id: Optional[str] = None,
        session_id: str = "",
        ip_address: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            actor=actor,
            target=target,
            severity=severity,
            details=details or {},
            trace_id=trace_id or str(uuid.uuid4())[:12],
            session_id=session_id,
            ip_address=ip_address,
        )
        entry.finalize(self._last_hash)
        self._last_hash = entry.hash_value

        self._entries.append(entry)
        self._action_counts[action.value] = self._action_counts.get(action.value, 0) + 1
        self._severity_counts[severity.value] = self._severity_counts.get(severity.value, 0) + 1
        self._actor_counts[actor] = self._actor_counts.get(actor, 0) + 1

        logger.debug(f"Audit: {action.value} by {actor} on {target}")
        return entry

    def query(
        self,
        actor: Optional[str] = None,
        action: Optional[AuditAction] = None,
        severity: Optional[AuditSeverity] = None,
        trace_id: Optional[str] = None,
        target: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEntry]:
        results = list(self._entries)

        if actor:
            results = [e for e in results if actor.lower() in e.actor.lower()]
        if action:
            results = [e for e in results if e.action == action]
        if severity:
            results = [e for e in results if e.severity == severity]
        if trace_id:
            results = [e for e in results if trace_id in e.trace_id]
        if target:
            results = [e for e in results if target.lower() in e.target.lower()]
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]

        return results[offset:offset + limit]

    def verify_integrity(self) -> Dict:
        verified = 0
        failed = 0
        prev_hash = ""
        for entry in self._entries:
            expected = entry.compute_hash()
            if entry.hash_value == expected and entry.previous_hash == prev_hash:
                verified += 1
            else:
                failed += 1
            prev_hash = entry.hash_value

        return {
            "verified": verified,
            "failed": failed,
            "total": len(self._entries),
            "integrityOk": failed == 0,
        }

    def get_statistics(self) -> Dict:
        return {
            "totalEntries": len(self._entries),
            "byAction": self._action_counts,
            "bySeverity": self._severity_counts,
            "byActor": self._actor_counts,
            "retentionDays": self._retention_days,
            "oldestEntry": self._entries[0].timestamp.isoformat() if self._entries else None,
            "newestEntry": self._entries[-1].timestamp.isoformat() if self._entries else None,
        }

    def cleanup_expired(self):
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        self._entries = [e for e in self._entries if e.timestamp >= cutoff]
        logger.info(f"Audit cleanup: retained {len(self._entries)} entries")

    def export(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json",
    ) -> str:
        entries = self.query(start_time=start_time, end_time=end_time, limit=10000)
        if format == "json":
            return json.dumps([e.to_dict() for e in entries], indent=2)
        return ""

    def to_dict(self) -> Dict:
        return {
            "totalEntries": len(self._entries),
            "retentionDays": self._retention_days,
            "lastHash": self._last_hash,
            "statistics": self.get_statistics(),
        }
