"""Alert Escalation Manager.

Manages escalation policies for alerts that are not resolved within time limits.
Supports multi-level escalation with different channels per level.

Example escalation chain:
    Level 0 (0-5min):  Console only
    Level 1 (5-15min): Slack notification
    Level 2 (15-30min): Email + Webhook
    Level 3 (30min+):     Emergency call (stub)

Usage::

    mgr = EscalationManager()
    mgr.add_policy(EscalationPolicy(
        name="critical_alerts",
        severity_filter=[AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY],
        levels=[
            EscalationLevel(delay_seconds=0, channels=["console"]),
            EscalationLevel(delay_seconds=300, channels=["slack_ops"]),
            EscalationLevel(delay_seconds=900, channels=["email_ops", "webhook"]),
        ],
    ))
    mgr.check_escalations(active_alerts, notifier)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.monitoring.alert.rule_engine import Alert, AlertSeverity
from services.monitoring.alert.notifier import AlertNotifier


@dataclass
class EscalationLevel:
    """A level in the escalation chain."""

    delay_seconds: float  # How long after alert fires to trigger this level
    channels: List[str] = field(default_factory=list)  # Channel names to notify
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delay_seconds": self.delay_seconds,
            "channels": self.channels,
            "description": self.description,
        }


@dataclass
class EscalationPolicy:
    """An escalation policy for a category of alerts."""

    name: str
    levels: List[EscalationLevel] = field(default_factory=list)
    severity_filter: Optional[List[AlertSeverity]] = None
    category_filter: Optional[List[str]] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "levels": [lvl.to_dict() for lvl in self.levels],
            "severity_filter": [s.value for s in self.severity_filter] if self.severity_filter else None,
            "category_filter": self.category_filter,
            "enabled": self.enabled,
        }

    def matches(self, alert: Alert) -> bool:
        """Check if this policy applies to an alert."""
        if not self.enabled:
            return False
        if self.severity_filter and alert.severity not in self.severity_filter:
            return False
        if self.category_filter and alert.category not in self.category_filter:
            return False
        return True


class EscalationManager:
    """Manages alert escalation across time-based levels.

    When an alert fires and is not resolved, it escalates through
    defined levels, notifying more channels at each level.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, EscalationPolicy] = {}
        self._escalation_state: Dict[str, int] = {}  # alert_id → current level index

    def add_policy(self, policy: EscalationPolicy) -> None:
        """Register an escalation policy."""
        # Sort levels by delay
        policy.levels = sorted(policy.levels, key=lambda l: l.delay_seconds)
        self._policies[policy.name] = policy

    def remove_policy(self, name: str) -> None:
        """Remove an escalation policy."""
        self._policies.pop(name, None)

    def get_policy(self, name: str) -> Optional[EscalationPolicy]:
        """Get a policy by name."""
        return self._policies.get(name)

    def list_policies(self) -> List[EscalationPolicy]:
        """List all escalation policies."""
        return list(self._policies.values())

    def check_escalations(
        self,
        active_alerts: List[Alert],
        notifier: AlertNotifier,
    ) -> List[str]:
        """Check all active alerts and escalate if needed.

        Returns list of alert IDs that were escalated.
        """
        now = time.time()
        escalated: List[str] = []

        for alert in active_alerts:
            for policy in self._policies.values():
                if not policy.matches(alert):
                    continue

                current_level = self._escalation_state.get(alert.alert_id, -1)
                alert_age = now - alert.fired_at

                for i, level in enumerate(policy.levels):
                    if i <= current_level:
                        continue  # Already escalated past this level
                    if alert_age >= level.delay_seconds and level.channels:
                        notifier.send(alert, channel_names=level.channels)
                        self._escalation_state[alert.alert_id] = i
                        escalated.append(alert.alert_id)

        # Clean up resolved alerts from state
        active_ids = {a.alert_id for a in active_alerts}
        stale = [aid for aid in self._escalation_state if aid not in active_ids]
        for aid in stale:
            del self._escalation_state[aid]

        return escalated

    def get_escalation_state(self, alert_id: str) -> int:
        """Get current escalation level for an alert (-1 = not escalated)."""
        return self._escalation_state.get(alert_id, -1)

    def reset_escalation(self, alert_id: str) -> None:
        """Reset escalation state for an alert."""
        self._escalation_state.pop(alert_id, None)

    def get_status(self) -> Dict[str, Any]:
        """Get escalation manager status."""
        return {
            "policies_count": len(self._policies),
            "active_escalations": len(self._escalation_state),
            "policies": [p.to_dict() for p in self._policies.values()],
        }
