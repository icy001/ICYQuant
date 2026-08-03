"""
Service Level Objective (SLO) framework.

Defines SLO targets for availability,
latency, and error budget tracking.

SLOs represent the desired level of
service that the platform commits to
maintain, enabling error budget-based
release management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class SLO:
    """
    Service Level Objective.

    Represents a measurable target for
    service quality, including availability,
    latency, and error budget.

    Attributes:
        name: SLO name.
        availability: Target availability (0-1).
        latency_ms: Target latency in milliseconds.
        error_budget: Allowed error budget (0-1).
        window_days: SLO evaluation window.
        description: Human-readable description.
    """

    name: str = "default"
    availability: float = 0.999
    latency_ms: float = 100.0
    error_budget: float = 0.001
    window_days: int = 30
    description: str = ""

    def __post_init__(
        self,
    ) -> None:
        """Validate SLO parameters."""

        if not 0 <= self.availability <= 1:
            raise ValueError(
                f"availability must be 0-1, got {self.availability}"
            )
        if not 0 <= self.error_budget <= 1:
            raise ValueError(
                f"error_budget must be 0-1, got {self.error_budget}"
            )
        if self.latency_ms < 0:
            raise ValueError(
                f"latency_ms must be >= 0, got {self.latency_ms}"
            )

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
            1 - self.availability
        ) * 86400

    @property
    def allowed_errors_per_window(
        self,
    ) -> float:
        """
        Calculate allowed errors per SLO window.

        Returns:
            Maximum allowed error count.
        """

        return self.error_budget * (
            self.window_days * 86400
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
            "name": self.name,
            "availability": self.availability,
            "latency_ms": self.latency_ms,
            "error_budget": self.error_budget,
            "window_days": self.window_days,
            "description": self.description,
            "allowed_downtime_per_day": (
                self.allowed_downtime_per_day
            ),
            "allowed_errors_per_window": (
                self.allowed_errors_per_window
            ),
        }


@dataclass
class SLOStatus:
    """
    SLO compliance status.

    Tracks current SLO performance
    against targets for real-time
    error budget burn rate monitoring.

    Attributes:
        slo: The SLO definition.
        current_availability: Measured availability.
        current_latency_ms: Measured latency.
        current_error_rate: Measured error rate.
        error_budget_remaining: Remaining budget (0-1).
        burn_rate: Error budget burn rate.
        timestamp: Measurement timestamp.
    """

    slo: SLO
    current_availability: float = 1.0
    current_latency_ms: float = 0.0
    current_error_rate: float = 0.0
    error_budget_remaining: float = 1.0
    burn_rate: float = 0.0
    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    @property
    def is_compliant(
        self,
    ) -> bool:
        """Check if SLO is currently met."""

        return (
            self.current_availability
            >= self.slo.availability
            and self.current_latency_ms
            <= self.slo.latency_ms
        )

    @property
    def budget_status(
        self,
    ) -> str:
        """Get error budget status string."""

        if self.error_budget_remaining > 0.5:
            return "healthy"
        elif self.error_budget_remaining > 0.2:
            return "warning"
        elif self.error_budget_remaining > 0:
            return "critical"
        return "exhausted"

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "slo": self.slo.to_dict(),
            "current_availability": (
                self.current_availability
            ),
            "current_latency_ms": (
                self.current_latency_ms
            ),
            "current_error_rate": (
                self.current_error_rate
            ),
            "error_budget_remaining": (
                self.error_budget_remaining
            ),
            "burn_rate": self.burn_rate,
            "is_compliant": self.is_compliant,
            "budget_status": self.budget_status,
            "timestamp": self.timestamp.isoformat(),
        }
