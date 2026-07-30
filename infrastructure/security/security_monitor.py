"""
ICYQuant Security Monitor

Real-time monitoring of security events: anomalous login,
token anomalies, brute force, privilege escalation, secret leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class SecurityEventType(str, Enum):
    ANOMALOUS_LOGIN = "anomalous_login"
    ANOMALOUS_TOKEN = "anomalous_token"
    BRUTE_FORCE = "brute_force"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SECRET_LEAKAGE = "secret_leakage"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    POLICY_VIOLATION = "policy_violation"


class AlertSeverity(str, Enum):
    INFORMATIONAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SecurityAlert:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SecurityEventType = SecurityEventType.ANOMALOUS_LOGIN
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = ""
    description: str = ""
    source: str = ""
    user_id: str = ""
    ip_address: str = ""
    details: Dict = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def acknowledge(self):
        self.acknowledged = True

    def resolve(self):
        self.resolved = True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "eventType": self.event_type.value,
            "severity": self.severity.name,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "userId": self.user_id,
            "ipAddress": self.ip_address,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "createdAt": self.created_at.isoformat(),
        }


class SecurityMonitor:
    """
    Real-time security event monitoring.

    Detects anomalous logins, brute force attacks, privilege escalation,
    and secret leakage. Generates alerts for security incidents.
    """

    def __init__(self):
        self._alerts: List[SecurityAlert] = []
        self._event_handlers: Dict[SecurityEventType, List[Callable]] = {}
        self._alert_handlers: List[Callable] = []
        self._failed_login_attempts: Dict[str, List[datetime]] = {}
        self._user_ips: Dict[str, Set[str]] = {}
        self._token_usage: Dict[str, List[datetime]] = {}
        self._max_alerts = 10000

    def record_login_attempt(
        self,
        user_id: str,
        ip_address: str,
        successful: bool = True,
    ):
        now = datetime.now()
        if successful:
            self._user_ips.setdefault(user_id, set()).add(ip_address)
            self._failed_login_attempts.pop(user_id, None)
            return

        attempts = self._failed_login_attempts.setdefault(user_id, [])
        attempts.append(now)

        window = timedelta(minutes=5)
        recent = [a for a in attempts if now - a < window]
        self._failed_login_attempts[user_id] = recent

        if len(recent) >= 5:
            self._raise_alert(
                event_type=SecurityEventType.BRUTE_FORCE,
                severity=AlertSeverity.HIGH,
                title=f"Brute force detected for {user_id}",
                description=f"Multiple failed login attempts from {ip_address}",
                user_id=user_id,
                ip_address=ip_address,
            )

    def check_anomalous_login(self, user_id: str, ip_address: str) -> bool:
        known_ips = self._user_ips.get(user_id, set())
        if ip_address not in known_ips and len(known_ips) > 0:
            self._raise_alert(
                event_type=SecurityEventType.ANOMALOUS_LOGIN,
                severity=AlertSeverity.MEDIUM,
                title=f"Anomalous login for {user_id}",
                description=f"Login from unknown IP: {ip_address}",
                user_id=user_id,
                ip_address=ip_address,
                details={"knownIPs": list(known_ips)},
            )
            return True
        return False

    def check_token_abuse(self, token_id: str) -> bool:
        now = datetime.now()
        timestamps = self._token_usage.setdefault(token_id, [])
        timestamps.append(now)

        window = timedelta(minutes=1)
        recent = [t for t in timestamps if now - t < window]
        self._token_usage[token_id] = recent

        if len(recent) >= 100:
            self._raise_alert(
                event_type=SecurityEventType.ANOMALOUS_TOKEN,
                severity=AlertSeverity.HIGH,
                title=f"Token abuse detected",
                description=f"Token {token_id} used {len(recent)} times in 1 minute",
            )
            return True
        return False

    def check_privilege_escalation(
        self,
        user_id: str,
        old_role: str,
        new_role: str,
    ):
        high_privilege_roles = {"admin", "super_admin", "root"}
        if new_role in high_privilege_roles and old_role not in high_privilege_roles:
            self._raise_alert(
                event_type=SecurityEventType.PRIVILEGE_ESCALATION,
                severity=AlertSeverity.CRITICAL,
                title=f"Privilege escalation: {user_id}",
                description=f"User {user_id} escalated from {old_role} to {new_role}",
                user_id=user_id,
                details={"oldRole": old_role, "newRole": new_role},
            )

    def check_secret_leakage(self, secret_name: str, exposed_in: str):
        self._raise_alert(
            event_type=SecurityEventType.SECRET_LEAKAGE,
            severity=AlertSeverity.CRITICAL,
            title=f"Secret leakage detected: {secret_name}",
            description=f"Secret '{secret_name}' may be exposed in {exposed_in}",
            details={"secretName": secret_name, "exposedIn": exposed_in},
        )

    def on_event(self, event_type: SecurityEventType, handler: Callable):
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def on_alert(self, handler: Callable):
        self._alert_handlers.append(handler)

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[SecurityEventType] = None,
        unresolved_only: bool = False,
        limit: int = 100,
    ) -> List[SecurityAlert]:
        alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a.severity.value >= severity.value]
        if event_type:
            alerts = [a for a in alerts if a.event_type == event_type]
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        return alerts[-limit:]

    def acknowledge_alert(self, alert_id: str):
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledge()

    def resolve_alert(self, alert_id: str):
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolve()

    def get_statistics(self) -> Dict:
        return {
            "totalAlerts": len(self._alerts),
            "unresolvedAlerts": sum(1 for a in self._alerts if not a.resolved),
            "criticalAlerts": sum(1 for a in self._alerts if a.severity == AlertSeverity.CRITICAL),
            "byEventType": self._count_by_event(),
        }

    def _count_by_event(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for alert in self._alerts:
            key = alert.event_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _raise_alert(self, event_type: SecurityEventType, severity: AlertSeverity, **kwargs):
        alert = SecurityAlert(
            event_type=event_type,
            severity=severity,
            **kwargs,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(alert)
            except Exception:
                logger.error(f"Event handler error: {e}")

        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception:
                pass

    def to_dict(self) -> Dict:
        return {
            "statistics": self.get_statistics(),
        }
