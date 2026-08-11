"""
Governance Heartbeat — governance component health check signals.

Part 1.5: periodic heartbeat signals for each governance component,
consumed by the watchdog and control plane health monitoring.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class GovernanceHeartbeat:
    """Heartbeat signal from a governance component."""

    heartbeat_id: str = field(default_factory=lambda: f"HB-{uuid.uuid4().hex[:12].upper()}")
    component: str = ""        # Component name (e.g., "control-plane", "risk-guardian")
    status: str = "HEALTHY"    # HEALTHY / DEGRADED / UNHEALTHY
    message: str = ""

    # Version info
    version: str = ""
    uptime_seconds: float = 0.0

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Timing
    sent_at: float = field(default_factory=time.time)
    correlation_id: str = ""

    @property
    def is_healthy(self) -> bool:
        return self.status == "HEALTHY"

    @property
    def is_degraded(self) -> bool:
        return self.status == "DEGRADED"

    @property
    def is_unhealthy(self) -> bool:
        return self.status == "UNHEALTHY"

    @property
    def age_seconds(self) -> float:
        """Seconds since this heartbeat was sent."""
        return time.time() - self.sent_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heartbeat_id": self.heartbeat_id,
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "sent_at": self.sent_at,
            "age_seconds": self.age_seconds,
        }

    @classmethod
    def healthy(cls, component: str, version: str = "", uptime: float = 0.0) -> "GovernanceHeartbeat":
        return cls(
            component=component,
            status="HEALTHY",
            version=version,
            uptime_seconds=uptime,
            message=f"{component} is healthy.",
        )

    @classmethod
    def degraded(cls, component: str, message: str) -> "GovernanceHeartbeat":
        return cls(
            component=component,
            status="DEGRADED",
            message=message,
        )

    @classmethod
    def unhealthy(cls, component: str, message: str) -> "GovernanceHeartbeat":
        return cls(
            component=component,
            status="UNHEALTHY",
            message=message,
        )
