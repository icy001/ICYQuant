"""
Alert data models.

Defines the core data structures for
the alerting system, including alert
levels, alert events, and alert states.

These models are used by the AlertEngine,
RuleEvaluator, AlertRouter, and
EscalationPolicy components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AlertLevel(str, Enum):
    """
    Alert severity levels.

    Ordered by severity from least
    to most critical. Used by the
    notification router and escalation
    policy to determine urgency.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def weight(
        self,
    ) -> int:
        """Get numeric weight for comparison."""
        return {
            AlertLevel.INFO: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.ERROR: 2,
            AlertLevel.CRITICAL: 3,
        }[self]

    @classmethod
    def from_string(
        cls,
        value: str,
    ) -> "AlertLevel":
        """
        Parse alert level from string.

        Args:
            value: Level string.

        Returns:
            AlertLevel enum member.

        Raises:
            ValueError: If string is invalid.
        """

        for member in cls:
            if member.value == value.lower():
                return member
        raise ValueError(
            f"Invalid alert level: {value}"
        )


class AlertState(str, Enum):
    """
    Alert lifecycle state.

    Tracks the progression of an
    alert from initial firing through
    resolution.
    """

    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


@dataclass
class AlertEvent:
    """
    A single alert event.

    Represents a metric threshold
    breach that has been detected
    by the RuleEvaluator and routed
    by the AlertRouter.

    Attributes:
        rule: Rule name that triggered.
        level: Alert severity level.
        metric: Metric name that breached.
        value: Current metric value.
        threshold: Configured threshold.
        timestamp: When the alert fired.
        labels: Additional alert labels.
        message: Human-readable message.
        state: Current alert state.
        fingerprint: Unique alert identifier.
    """

    rule: str
    level: AlertLevel
    metric: str
    value: float
    threshold: float
    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )
    labels: Dict[str, str] = field(
        default_factory=dict
    )
    message: str = ""
    state: AlertState = AlertState.FIRING
    fingerprint: str = ""

    def __post_init__(
        self,
    ) -> None:
        """Generate fingerprint if not provided."""

        if not self.fingerprint:
            self.fingerprint = (
                f"{self.rule}:{self.metric}"
            )

        if not self.message:
            self.message = (
                f"Alert '{self.rule}': "
                f"metric '{self.metric}' "
                f"value {self.value} "
                f"breached threshold {self.threshold}"
            )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "rule": self.rule,
            "level": self.level.value,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "message": self.message,
            "state": self.state.value,
            "fingerprint": self.fingerprint,
        }


@dataclass
class AlertHistory:
    """
    Alert history record.

    Tracks fired alerts for
    audit and deduplication.

    Attributes:
        events: List of alert events.
        max_size: Maximum history size.
    """

    events: List[AlertEvent] = field(
        default_factory=list
    )
    max_size: int = 1000

    def add(
        self,
        event: AlertEvent,
    ) -> None:
        """
        Add an alert event to history.

        Args:
            event: Alert event to add.
        """

        self.events.append(event)
        if len(self.events) > self.max_size:
            self.events = self.events[
                -self.max_size:
            ]

    def get_recent(
        self,
        seconds: float = 300,
    ) -> List[AlertEvent]:
        """
        Get recent alert events.

        Args:
            seconds: Look-back window in seconds.

        Returns:
            List of recent events.
        """

        now = datetime.utcnow()
        return [
            e
            for e in self.events
            if (now - e.timestamp).total_seconds()
            <= seconds
        ]

    def clear(
        self,
    ) -> None:
        """Clear all history."""

        self.events.clear()

    @property
    def count(
        self,
    ) -> int:
        """Get total event count."""
        return len(self.events)
