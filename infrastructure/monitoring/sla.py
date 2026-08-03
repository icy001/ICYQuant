"""
Service Level Agreement (SLA) framework.

Defines SLA contracts for uptime,
response time, and incident management.

SLAs represent external commitments
to customers, differing from SLOs
which are internal targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SLA:
    """
    Service Level Agreement.

    Represents an external commitment
    for service quality, including
    uptime guarantees, response time
    targets, and incident limits.

    Attributes:
        name: SLA name.
        uptime: Guaranteed uptime (0-1).
        response_time_ms: Max response time in ms.
        incident_count: Max allowed incidents per period.
        period_days: SLA evaluation period.
        penalty: Penalty for breach.
        description: Human-readable description.
    """

    name: str = "default"
    uptime: float = 0.999
    response_time_ms: float = 200.0
    incident_count: int = 3
    period_days: int = 30
    penalty: str = ""
    description: str = ""

    def __post_init__(
        self,
    ) -> None:
        """Validate SLA parameters."""

        if not 0 <= self.uptime <= 1:
            raise ValueError(
                f"uptime must be 0-1, got {self.uptime}"
            )
        if self.response_time_ms < 0:
            raise ValueError(
                f"response_time_ms must be >= 0"
            )
        if self.incident_count < 0:
            raise ValueError(
                f"incident_count must be >= 0"
            )

    @property
    def allowed_downtime_per_period(
        self,
    ) -> float:
        """
        Calculate allowed downtime per period in seconds.

        Returns:
            Maximum downtime in seconds per period.
        """

        return (
            1 - self.uptime
        ) * self.period_days * 86400

    @property
    def allowed_downtime_per_day(
        self,
    ) -> float:
        """
        Calculate allowed downtime per day in seconds.

        Returns:
            Maximum downtime in seconds per day.
        """

        return (
            1 - self.uptime
        ) * 86400

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "name": self.name,
            "uptime": self.uptime,
            "response_time_ms": self.response_time_ms,
            "incident_count": self.incident_count,
            "period_days": self.period_days,
            "penalty": self.penalty,
            "description": self.description,
            "allowed_downtime_per_period": (
                self.allowed_downtime_per_period
            ),
            "allowed_downtime_per_day": (
                self.allowed_downtime_per_day
            ),
        }


@dataclass
class SLAReport:
    """
    SLA compliance report.

    Tracks current SLA performance
    and breach status for reporting
    to stakeholders.

    Attributes:
        sla: The SLA definition.
        measured_uptime: Measured uptime ratio.
        measured_response_time_ms: Avg response time.
        measured_incidents: Incident count this period.
        is_breached: Whether SLA is breached.
        timestamp: Report timestamp.
    """

    sla: SLA
    measured_uptime: float = 1.0
    measured_response_time_ms: float = 0.0
    measured_incidents: int = 0
    is_breached: bool = False
    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    def __post_init__(
        self,
    ) -> None:
        """Auto-calculate breach status."""

        self.is_breached = (
            self.measured_uptime < self.sla.uptime
            or self.measured_response_time_ms
            > self.sla.response_time_ms
            or self.measured_incidents
            > self.sla.incident_count
        )

    @property
    def uptime_delta(
        self,
    ) -> float:
        """Get uptime margin (positive = OK)."""

        return self.measured_uptime - self.sla.uptime

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "sla": self.sla.to_dict(),
            "measured_uptime": self.measured_uptime,
            "measured_response_time_ms": (
                self.measured_response_time_ms
            ),
            "measured_incidents": (
                self.measured_incidents
            ),
            "is_breached": self.is_breached,
            "uptime_delta": self.uptime_delta,
            "timestamp": self.timestamp.isoformat(),
        }
