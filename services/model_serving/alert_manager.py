"""
ICYQuant Alert Manager — Unified alerting for model serving.

Aggregates alerts from all monitoring subsystems:
  - Performance alerts (latency, error rate, throughput)
  - Prediction alerts (distribution drift, frozen predictions)
  - Model alerts (health, staleness, failures)
  - Drift alerts (data, feature, prediction drift)
  - Deployment alerts (rollback, canary health)

Provides:
  - Alert rule configuration
  - Alert deduplication
  - Alert severity levels
  - Channel routing (log, metrics, webhook, email)
  - Alert suppression windows
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Alert severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert lifecycle state."""
    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCategory(str, Enum):
    """Alert category."""
    PERFORMANCE = "performance"
    PREDICTION = "prediction"
    MODEL_HEALTH = "model_health"
    DRIFT = "drift"
    DEPLOYMENT = "deployment"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class AlertRule:
    """An alerting rule."""
    name: str
    category: AlertCategory
    description: str
    severity: Severity
    condition: str  # e.g. "error_rate > 0.1"
    cooldown_seconds: int = 300  # Minimum interval between firing
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """A triggered alert."""
    alert_id: str
    rule_name: str
    category: AlertCategory
    severity: Severity
    message: str
    model_id: Optional[str] = None
    state: AlertState = AlertState.FIRING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "model_id": self.model_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class AlertStats:
    """Alert statistics."""
    total_fired: int = 0
    by_severity: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_category: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    resolved: int = 0
    firing: int = 0


# ---------------------------------------------------------------------------
# Alert Manager
# ---------------------------------------------------------------------------

class AlertManager:
    """Central alert management system.

    Usage::

        manager = AlertManager()
        manager.register_rule(AlertRule(...))
        manager.on_alert(lambda alert: print(alert.message))

        await manager.fire(
            category=AlertCategory.PERFORMANCE,
            severity=Severity.WARNING,
            model_id="nvda_model",
            message="P99 latency exceeded 100ms",
        )
    """

    def __init__(self):
        self._initialized = False

        # Alert rules
        self._rules: Dict[str, AlertRule] = {}

        # Active alerts
        self._alerts: Dict[str, Alert] = {}
        self._alert_history: deque[Alert] = deque(maxlen=1000)

        # Cooldown tracking: (rule_name, model_id) → last_fired_time
        self._cooldowns: Dict[str, float] = {}

        # Deduplication: (rule_name, model_id) → alert_id
        self._active_alert_keys: Dict[str, str] = {}

        # Stats
        self._stats = AlertStats()

        # Callbacks
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._webhook_urls: List[str] = []

        # Alert counter
        self._alert_counter: int = 0

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("AlertManager initialized — %d rules", len(self._rules))

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def register_rule(self, rule: AlertRule) -> None:
        """Register an alerting rule."""
        self._rules[rule.name] = rule

    def unregister_rule(self, rule_name: str) -> None:
        self._rules.pop(rule_name, None)

    def get_rule(self, rule_name: str) -> Optional[AlertRule]:
        return self._rules.get(rule_name)

    def list_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": r.name,
                "category": r.category.value,
                "severity": r.severity.value,
                "condition": r.condition,
                "enabled": r.enabled,
            }
            for r in self._rules.values()
        ]

    # ------------------------------------------------------------------
    # Fire alerts
    # ------------------------------------------------------------------

    async def fire(
        self,
        category: AlertCategory,
        severity: Severity,
        message: str,
        *,
        model_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        cooldown_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """Fire an alert.

        Enforces:
          - Rule enablement
          - Cooldown period (deduplication)
          - Severity routing

        Args:
            category: Alert category.
            severity: Alert severity.
            message: Human-readable alert message.
            model_id: Related model identifier.
            rule_name: Associated rule name.
            cooldown_seconds: Minimum interval between identical alerts.
            metadata: Additional alert metadata.

        Returns:
            Alert object if fired, None if suppressed.
        """
        # Check rule
        if rule_name:
            rule = self._rules.get(rule_name)
            if rule and not rule.enabled:
                return None
            if rule:
                cooldown_seconds = cooldown_seconds or rule.cooldown_seconds

        # Check cooldown
        cooldown_key = f"{rule_name or category.value}:{model_id or 'global'}"
        last_fired = self._cooldowns.get(cooldown_key)
        if last_fired and cooldown_seconds:
            if time.time() - last_fired < cooldown_seconds:
                return None  # Suppressed

        # De-duplicate: resolve existing firing alert
        existing_id = self._active_alert_keys.get(cooldown_key)
        if existing_id and existing_id in self._alerts:
            # Update existing alert instead of creating new one
            existing = self._alerts[existing_id]
            existing.message = message
            existing.metadata = metadata or {}
            return existing

        # Create alert
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}_{int(time.time())}"

        alert = Alert(
            alert_id=alert_id,
            rule_name=rule_name or category.value,
            category=category,
            severity=severity,
            message=message,
            model_id=model_id,
            metadata=metadata or {},
        )

        self._alerts[alert_id] = alert
        self._alert_history.append(alert)
        self._active_alert_keys[cooldown_key] = alert_id
        self._cooldowns[cooldown_key] = time.time()

        # Stats
        self._stats.total_fired += 1
        self._stats.by_severity[severity.value] += 1
        self._stats.by_category[category.value] += 1
        self._stats.firing += 1
        if model_id:
            self._stats.by_model[model_id] += 1

        # Log
        log_level = {
            Severity.INFO: logging.INFO,
            Severity.WARNING: logging.WARNING,
            Severity.ERROR: logging.ERROR,
            Severity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.WARNING)

        logger.log(log_level, "[%s] %s: %s", severity.value.upper(),
                   model_id or "system", message)

        # Notify callbacks
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception as exc:
                logger.error("Alert callback failed: %s", exc)

        return alert

    async def resolve(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return False

        alert.state = AlertState.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc).isoformat()
        self._stats.firing = max(0, self._stats.firing - 1)
        self._stats.resolved += 1

        # Clean up active alert key
        cooldown_key = f"{alert.rule_name}:{alert.model_id or 'global'}"
        self._active_alert_keys.pop(cooldown_key, None)

        return True

    async def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return False
        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
        return True

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    async def fire_performance(
        self,
        model_id: str,
        message: str,
        severity: Severity = Severity.WARNING,
    ) -> Optional[Alert]:
        return await self.fire(
            category=AlertCategory.PERFORMANCE,
            severity=severity,
            message=message,
            model_id=model_id,
        )

    async def fire_drift(
        self,
        model_id: str,
        message: str,
        severity: Severity = Severity.WARNING,
    ) -> Optional[Alert]:
        return await self.fire(
            category=AlertCategory.DRIFT,
            severity=severity,
            message=message,
            model_id=model_id,
        )

    async def fire_model_health(
        self,
        model_id: str,
        message: str,
        severity: Severity = Severity.ERROR,
    ) -> Optional[Alert]:
        return await self.fire(
            category=AlertCategory.MODEL_HEALTH,
            severity=severity,
            message=message,
            model_id=model_id,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_alert(self, callback: Callable[[Alert], None]) -> None:
        """Register alert notification callback."""
        self._alert_callbacks.append(callback)

    def add_webhook(self, url: str) -> None:
        """Add a webhook URL for alert notifications."""
        self._webhook_urls.append(url)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all currently firing alerts."""
        return [
            a.to_dict() for a in self._alerts.values()
            if a.state == AlertState.FIRING
        ]

    def get_alerts_by_model(self, model_id: str) -> List[Dict[str, Any]]:
        """Get alerts for a specific model."""
        return [
            a.to_dict() for a in self._alert_history
            if a.model_id == model_id
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_fired": self._stats.total_fired,
            "by_severity": dict(self._stats.by_severity),
            "by_category": dict(self._stats.by_category),
            "resolved": self._stats.resolved,
            "firing": self._stats.firing,
            "active_alerts": self._stats.firing,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "rules": len(self._rules),
            "active_alerts": self._stats.firing,
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return f"AlertManager(rules={len(self._rules)}, active={self._stats.firing})"
