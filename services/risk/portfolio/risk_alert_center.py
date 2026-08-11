"""
Risk Alert Center — Unified multi-level risk alerting system.

Processes risk events from all monitors and engines, categorizes
them by severity, and generates structured alerts for dispatch.

Architecture::

    Risk Events → Severity Classification → Alert Enrichment → Alert Queue
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class AlertStatus(str, Enum):
    """Alert lifecycle status."""
    CREATED = "CREATED"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


@dataclass
class RiskAlert:
    """Structured risk alert."""
    alert_id: str
    severity: AlertSeverity
    source: str
    title: str
    message: str
    account_id: str = ""
    risk_score: float = 0.0
    triggered_rules: list[str] = field(default_factory=list)
    breach_details: list[dict[str, Any]] = field(default_factory=list)
    status: AlertStatus = AlertStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: str = ""
    resolution_note: str = ""
    ttl_seconds: int = 3600
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.status in (AlertStatus.RESOLVED, AlertStatus.EXPIRED):
            return True
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "account_id": self.account_id,
            "risk_score": self.risk_score,
            "triggered_rules": self.triggered_rules,
            "breach_details": self.breach_details,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class RiskAlertCenter:
    """
    Unified risk alerting system.

    Receives risk events from monitors and engines, classifies them
    by severity, enriches with context, and manages alert lifecycle
    (create, dispatch, acknowledge, resolve).

    Usage::

        center = RiskAlertCenter()
        await center.initialize()

        alerts = await center.process_breaches(breaches, risk_level, snapshot)
        await center.dispatch(alerts)
    """

    def __init__(
        self,
        max_alerts: int = 1000,
        default_ttl_seconds: int = 3600,
        escalation_timeout_seconds: int = 300,
    ) -> None:
        self._max_alerts = max_alerts
        self._default_ttl = default_ttl_seconds
        self._escalation_timeout = escalation_timeout_seconds

        self._alerts: deque[RiskAlert] = deque(maxlen=max_alerts)
        self._active_alerts: dict[str, RiskAlert] = {}
        self._alert_counter: int = 0
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the alert center."""
        self._initialized = True
        logger.info("RiskAlertCenter initialized.")

    async def stop(self) -> None:
        """Stop the alert center."""
        self._initialized = False
        logger.info("RiskAlertCenter stopped.")

    # ---- Core API ----

    async def process_breaches(
        self,
        breaches: list[dict[str, Any]],
        risk_level: str,
        account_id: str = "",
        source: str = "portfolio_monitor",
        snapshot: Any = None,
    ) -> list[RiskAlert]:
        """
        Process breach events and generate alerts.

        Returns a list of RiskAlert objects for dispatch.
        """
        alerts = []

        for breach in breaches:
            severity = self._map_breach_severity(breach, risk_level)

            self._alert_counter += 1
            alert = RiskAlert(
                alert_id=f"ALERT-{self._alert_counter:08d}",
                severity=severity,
                source=source,
                title=f"[{severity.value}] {breach.get('type', 'Unknown').upper()} Breach",
                message=breach.get("message", "Risk limit breached"),
                account_id=account_id or breach.get("account_id", ""),
                risk_score=breach.get("current", 0) if isinstance(breach.get("current"), (int, float)) else 50.0,
                triggered_rules=[breach.get("type", "unknown")],
                breach_details=[breach],
                ttl_seconds=self._default_ttl,
                metadata={
                    "breach_type": breach.get("type", ""),
                    "limit": breach.get("limit", 0),
                    "current": breach.get("current", 0),
                },
            )

            async with self._lock:
                self._alerts.append(alert)
                self._active_alerts[alert.alert_id] = alert

            alerts.append(alert)

        if alerts:
            logger.info(
                f"Generated {len(alerts)} alerts from {len(breaches)} breaches "
                f"(level={risk_level})"
            )

        return alerts

    async def create_alert(
        self,
        severity: AlertSeverity,
        source: str,
        title: str,
        message: str,
        account_id: str = "",
        risk_score: float = 0.0,
        triggered_rules: Optional[list[str]] = None,
        breach_details: Optional[list[dict[str, Any]]] = None,
        ttl_seconds: int = 0,
    ) -> RiskAlert:
        """Create a manual alert."""
        self._alert_counter += 1
        alert = RiskAlert(
            alert_id=f"ALERT-{self._alert_counter:08d}",
            severity=severity,
            source=source,
            title=title,
            message=message,
            account_id=account_id,
            risk_score=risk_score,
            triggered_rules=triggered_rules or [],
            breach_details=breach_details or [],
            ttl_seconds=ttl_seconds or self._default_ttl,
        )

        async with self._lock:
            self._alerts.append(alert)
            self._active_alerts[alert.alert_id] = alert

        logger.info(f"Alert created: {alert.alert_id} [{severity.value}] {title}")
        return alert

    # ---- Alert Lifecycle ----

    async def acknowledge(
        self, alert_id: str, acknowledged_by: str = ""
    ) -> Optional[RiskAlert]:
        """Acknowledge an alert."""
        async with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return None
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
        logger.info(f"Alert acknowledged: {alert_id} by {acknowledged_by}")
        return alert

    async def resolve(
        self, alert_id: str, resolution_note: str = ""
    ) -> Optional[RiskAlert]:
        """Resolve an alert."""
        async with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return None
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolution_note = resolution_note
        logger.info(f"Alert resolved: {alert_id}")
        return alert

    async def escalate(self, alert_id: str) -> Optional[RiskAlert]:
        """Escalate an alert to next severity level."""
        async with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return None

            escalation_map = {
                AlertSeverity.INFO: AlertSeverity.WARNING,
                AlertSeverity.WARNING: AlertSeverity.HIGH,
                AlertSeverity.HIGH: AlertSeverity.CRITICAL,
                AlertSeverity.CRITICAL: AlertSeverity.EMERGENCY,
                AlertSeverity.EMERGENCY: AlertSeverity.EMERGENCY,
            }
            new_severity = escalation_map.get(alert.severity, alert.severity)
            if new_severity != alert.severity:
                alert.severity = new_severity
                alert.status = AlertStatus.ESCALATED
                logger.warning(f"Alert escalated: {alert_id} → {new_severity.value}")

        return alert

    # ---- Query ----

    async def get_active_alerts(
        self,
        min_severity: Optional[AlertSeverity] = None,
    ) -> list[RiskAlert]:
        """Get active (unresolved) alerts, optionally filtered by severity."""
        async with self._lock:
            active = [
                a for a in self._active_alerts.values()
                if a.status not in (AlertStatus.RESOLVED, AlertStatus.EXPIRED)
                and not a.is_expired
            ]
            if min_severity:
                severity_order = {
                    AlertSeverity.INFO: 0,
                    AlertSeverity.WARNING: 1,
                    AlertSeverity.HIGH: 2,
                    AlertSeverity.CRITICAL: 3,
                    AlertSeverity.EMERGENCY: 4,
                }
                active = [
                    a for a in active
                    if severity_order.get(a.severity, 0) >= severity_order.get(min_severity, 0)
                ]
            return active

    async def get_alert(self, alert_id: str) -> Optional[RiskAlert]:
        """Get a specific alert by ID."""
        return self._active_alerts.get(alert_id)

    async def get_stats(self) -> dict[str, Any]:
        """Get alert center statistics."""
        async with self._lock:
            total = len(self._alerts)
            active = len([
                a for a in self._active_alerts.values()
                if a.status not in (AlertStatus.RESOLVED, AlertStatus.EXPIRED)
            ])
            by_severity = {}
            for a in self._active_alerts.values():
                sev = a.severity.value
                by_severity[sev] = by_severity.get(sev, 0) + 1

            return {
                "total_alerts": total,
                "active_alerts": active,
                "by_severity": by_severity,
            }

    # ---- Maintenance ----

    async def purge_expired(self) -> int:
        """Purge expired alerts from active tracking."""
        async with self._lock:
            expired = [
                aid for aid, a in self._active_alerts.items()
                if a.is_expired
            ]
            for aid in expired:
                self._active_alerts[aid].status = AlertStatus.EXPIRED
                del self._active_alerts[aid]
            return len(expired)

    # ---- Internal ----

    def _map_breach_severity(
        self, breach: dict[str, Any], risk_level: str
    ) -> AlertSeverity:
        """Map breach type and risk level to alert severity."""
        breach_type = breach.get("type", "")

        # Critical breaches always CRITICAL
        critical_types = {"margin", "drawdown", "kill_switch"}
        if breach_type in critical_types:
            return AlertSeverity.CRITICAL

        # Map by risk level
        level_map = {
            "CRITICAL": AlertSeverity.EMERGENCY,
            "HIGH": AlertSeverity.CRITICAL,
            "ELEVATED": AlertSeverity.HIGH,
            "WARNING": AlertSeverity.WARNING,
            "NORMAL": AlertSeverity.INFO,
        }
        return level_map.get(risk_level.upper(), AlertSeverity.WARNING)

    async def health_check(self) -> dict[str, Any]:
        """Check alert center health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_alerts": len(self._active_alerts),
            "total_alerts": len(self._alerts),
        }
