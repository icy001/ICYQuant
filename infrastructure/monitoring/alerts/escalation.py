"""
Escalation policy.

Manages alert escalation from lower
severity to higher severity channels
based on time-based or condition-based
escalation rules.

Escalation flow:
    Warning → Error → Critical → PagerDuty
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..alert_models import AlertEvent, AlertLevel


class EscalationPolicy:
    """
    Alert escalation policy.

    Defines escalation rules that
    promote alert severity and route
    to additional channels when an
    alert is not acknowledged within
    a configured timeout.

    Usage:
        policy = EscalationPolicy()

        policy.add_level(
            level=AlertLevel.WARNING,
            timeout=300,
            escalate_to=AlertLevel.ERROR,
        )
        policy.add_level(
            level=AlertLevel.ERROR,
            timeout=600,
            escalate_to=AlertLevel.CRITICAL,
        )

        escalated = await policy.check_escalation(alert)
    """

    def __init__(
        self,
    ) -> None:
        """Initialize escalation policy."""

        self._levels: Dict[AlertLevel, Dict[str, Any]] = {}
        self._fired_alerts: Dict[str, Dict[str, Any]] = {}

        # Default escalation chain
        self._levels[AlertLevel.INFO] = {
            "timeout": 300,
            "escalate_to": AlertLevel.WARNING,
        }
        self._levels[AlertLevel.WARNING] = {
            "timeout": 600,
            "escalate_to": AlertLevel.ERROR,
        }
        self._levels[AlertLevel.ERROR] = {
            "timeout": 900,
            "escalate_to": AlertLevel.CRITICAL,
        }
        self._levels[AlertLevel.CRITICAL] = {
            "timeout": 0,
            "escalate_to": None,
        }

    def add_level(
        self,
        level: AlertLevel,
        timeout: int,
        escalate_to: Optional[AlertLevel],
    ) -> None:
        """
        Configure escalation for a level.

        Args:
            level: Current alert level.
            timeout: Seconds before escalation.
            escalate_to: Target level to escalate to.
        """

        self._levels[level] = {
            "timeout": timeout,
            "escalate_to": escalate_to,
        }

    async def check_escalation(
        self,
        alert: AlertEvent,
    ) -> Optional[AlertEvent]:
        """
        Check if an alert should be escalated.

        Args:
            alert: Alert event to check.

        Returns:
            Escalated AlertEvent if escalated, None otherwise.
        """

        now = time.time()
        fingerprint = alert.fingerprint

        # Track alert if new
        if fingerprint not in self._fired_alerts:
            self._fired_alerts[fingerprint] = {
                "level": alert.level,
                "fired_at": now,
                "escalated": False,
            }
            return None

        tracked = self._fired_alerts[fingerprint]
        if tracked["escalated"]:
            return None

        current_level = tracked["level"]
        level_config = self._levels.get(current_level)

        if level_config is None:
            return None

        timeout = level_config["timeout"]
        escalate_to = level_config["escalate_to"]

        if timeout <= 0 or escalate_to is None:
            return None

        elapsed = now - tracked["fired_at"]
        if elapsed < timeout:
            return None

        # Escalate
        tracked["escalated"] = True
        escalated_event = AlertEvent(
            rule=alert.rule,
            level=escalate_to,
            metric=alert.metric,
            value=alert.value,
            threshold=alert.threshold,
            labels=alert.labels,
            message=(
                f"[ESCALATED] {alert.message} "
                f"(escalated from {current_level.value} "
                f"to {escalate_to.value})"
            ),
        )

        self._fired_alerts[escalated_event.fingerprint] = {
            "level": escalate_to,
            "fired_at": now,
            "escalated": False,
        }

        return escalated_event

    def acknowledge(
        self,
        fingerprint: str,
    ) -> bool:
        """
        Acknowledge an alert, stopping escalation.

        Args:
            fingerprint: Alert fingerprint.

        Returns:
            True if alert was found and acknowledged.
        """

        if fingerprint in self._fired_alerts:
            self._fired_alerts[fingerprint][
                "escalated"
            ] = True
            return True
        return False

    def resolve(
        self,
        fingerprint: str,
    ) -> None:
        """
        Mark an alert as resolved.

        Args:
            fingerprint: Alert fingerprint.
        """

        self._fired_alerts.pop(fingerprint, None)

    def get_pending(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Get pending (unacknowledged) alerts.

        Returns:
            List of pending alert info.
        """

        now = time.time()
        pending = []

        for fp, info in self._fired_alerts.items():
            if not info["escalated"]:
                level_config = self._levels.get(
                    info["level"]
                )
                timeout = (
                    level_config["timeout"]
                    if level_config
                    else 0
                )
                elapsed = now - info["fired_at"]
                remaining = max(
                    0, timeout - elapsed
                ) if timeout > 0 else 0
                pending.append({
                    "fingerprint": fp,
                    "level": info["level"].value,
                    "elapsed_seconds": elapsed,
                    "escalates_in_seconds": remaining,
                })

        return pending

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get escalation status.

        Returns:
            Status dictionary.
        """

        return {
            "levels": {
                level.value: config
                for level, config in self._levels.items()
            },
            "pending_count": len(
                self.get_pending()
            ),
            "tracked_count": len(self._fired_alerts),
        }
