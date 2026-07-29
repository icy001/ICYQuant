"""Alert Rule Engine.

Rule-based alerting system for ICYQuant platform.

Supports alert rules like:
- VaR > threshold → Risk Alert
- Drawdown > 10% → Critical Alert
- Broker latency > 300ms → Trading Alert
- Service DOWN → Infrastructure Alert

Usage::

    engine = AlertRuleEngine()
    engine.add_rule(AlertRule(
        name="high_drawdown",
        description="Drawdown exceeds 10%",
        severity=AlertSeverity.CRITICAL,
        condition_fn=lambda m: m.get("drawdown_pct", 0) > 10.0,
        category="risk",
    ))
    alerts = engine.evaluate(metrics_snapshot)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertState(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """A rule that triggers an alert when a condition is met."""

    name: str
    description: str
    severity: AlertSeverity
    condition_fn: Callable[[Dict[str, Any]], bool]
    category: str = "general"
    cooldown_seconds: float = 300.0  # Minimum time between re-firing
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)

    def evaluate(self, metrics: Dict[str, Any]) -> bool:
        """Check if this rule's condition is met."""
        if not self.enabled:
            return False
        try:
            return self.condition_fn(metrics)
        except Exception:
            return False


@dataclass
class Alert:
    """A triggered alert instance."""

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    rule_name: str = ""
    severity: AlertSeverity = AlertSeverity.INFO
    category: str = "general"
    message: str = ""
    state: AlertState = AlertState.FIRING
    fired_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.state = AlertState.RESOLVED
        self.resolved_at = time.time()

    def acknowledge(self, by: str = "system") -> None:
        """Acknowledge the alert."""
        self.state = AlertState.ACKNOWLEDGED
        self.acknowledged_at = time.time()
        self.acknowledged_by = by

    def suppress(self) -> None:
        """Suppress the alert."""
        self.state = AlertState.SUPPRESSED

    def duration_seconds(self) -> float:
        """How long this alert has been active."""
        end = self.resolved_at or time.time()
        return end - self.fired_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "state": self.state.value,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "duration_seconds": round(self.duration_seconds(), 1),
            "context": self.context,
            "labels": self.labels,
        }


class AlertRuleEngine:
    """Central alert rule evaluation engine.

    Holds all alert rules, evaluates them against metrics snapshots,
    and manages alert lifecycle (firing, resolution, suppression).
    """

    def __init__(self) -> None:
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._last_fired: Dict[str, float] = {}
        self._evaluation_count: int = 0

    def add_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> None:
        """Remove an alert rule."""
        self._rules.pop(name, None)

    def get_rule(self, name: str) -> Optional[AlertRule]:
        """Get a rule by name."""
        return self._rules.get(name)

    def list_rules(self) -> List[AlertRule]:
        """List all registered rules."""
        return list(self._rules.values())

    def evaluate(
        self,
        metrics: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Alert]:
        """Evaluate all rules against current metrics.

        Returns list of newly fired alerts.
        """
        self._evaluation_count += 1
        now = time.time()
        new_alerts: List[Alert] = []

        for rule in self._rules.values():
            # Check cooldown
            last_fired = self._last_fired.get(rule.name, 0)
            if now - last_fired < rule.cooldown_seconds:
                continue

            # Check if condition fires
            try:
                condition_met = rule.evaluate(metrics)
            except Exception:
                condition_met = False

            if condition_met:
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    category=rule.category,
                    message=f"[{rule.severity.value.upper()}] {rule.description}",
                    context=context or {},
                    labels=dict(rule.labels),
                )
                self._active_alerts[rule.name] = alert
                self._alert_history.append(alert)
                self._last_fired[rule.name] = now
                new_alerts.append(alert)
            else:
                # Auto-resolve if condition no longer met
                existing = self._active_alerts.pop(rule.name, None)
                if existing:
                    existing.resolve()
                    self._alert_history.append(existing)

        # Trim history
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-1000:]

        return new_alerts

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        category: Optional[str] = None,
    ) -> List[Alert]:
        """Get currently active (firing) alerts, optionally filtered."""
        alerts = list(self._active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if category:
            alerts = [a for a in alerts if a.category == category]
        return sorted(alerts, key=lambda a: a.fired_at, reverse=True)

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
    ) -> List[Alert]:
        """Get alert history."""
        history = list(self._alert_history)
        if severity:
            history = [a for a in history if a.severity == severity]
        return history[-limit:]

    def acknowledge_alert(self, alert_id: str, by: str = "operator") -> bool:
        """Acknowledge an active alert."""
        for alert in self._active_alerts.values():
            if alert.alert_id == alert_id:
                alert.acknowledge(by)
                return True
        return False

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert state."""
        active = self.get_active_alerts()
        return {
            "active_count": len(active),
            "by_severity": {
                s.value: len(self.get_active_alerts(severity=s))
                for s in AlertSeverity
            },
            "by_category": self._category_counts(active),
            "total_fired": len(self._alert_history),
            "evaluation_count": self._evaluation_count,
        }

    def _category_counts(self, alerts: List[Alert]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for a in alerts:
            counts[a.category] = counts.get(a.category, 0) + 1
        return counts
