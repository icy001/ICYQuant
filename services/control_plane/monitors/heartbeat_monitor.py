"""
HeartbeatMonitor — a single responsibility:

    read last heartbeat → compute elapsed → judge timeout → Health Decision

It must NOT restart components, halt trading or start recovery — those are
other layers. The monitor only produces a decision; the Control Plane turns
decisions into policy evaluation.

Timeline (defaults, configurable):

    0 ── warning_timeout ── critical_timeout ──▶  elapsed
    HEALTHY   │   DEGRADED   │   UNHEALTHY   │
              │  (10s)       │    (15s)      │

A component that never sent a heartbeat is allowed a startup grace period
before it is declared unhealthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..health.heartbeat import Heartbeat, utcnow


class HeartbeatDecision(str, Enum):
    """Decision produced by the heartbeat monitor."""

    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNRESPONSIVE = "UNRESPONSIVE"

    @property
    def is_healthy(self) -> bool:
        return self in (HeartbeatDecision.HEALTHY, HeartbeatDecision.STARTING)

    @property
    def missed(self) -> bool:
        return self in (
            HeartbeatDecision.DEGRADED,
            HeartbeatDecision.UNHEALTHY,
            HeartbeatDecision.UNRESPONSIVE,
        )


@dataclass
class HeartbeatHealthDecision:
    """Result of judging one heartbeat timeout evaluation."""

    component_id: str
    instance_id: str
    decision: HeartbeatDecision
    elapsed: float
    missed: bool
    last_sequence: Optional[int]
    last_seen: Optional[datetime]
    detected_at: datetime
    reason: str
    miss_count: int = 0

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "instance_id": self.instance_id,
            "decision": self.decision.value,
            "elapsed": self.elapsed,
            "missed": self.missed,
            "last_sequence": self.last_sequence,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "detected_at": self.detected_at.isoformat(),
            "reason": self.reason,
            "miss_count": self.miss_count,
        }


@dataclass
class HeartbeatMonitor:
    """Timeout-based heartbeat judge (stateless, values are injected)."""

    warning_timeout: float = 10.0
    critical_timeout: float = 15.0
    startup_grace_period: float = 30.0
    failure_threshold: int = 3

    def evaluate(
        self,
        heartbeat: Optional[Heartbeat],
        now: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        miss_count: int = 0,
    ) -> HeartbeatHealthDecision:
        """Judge the last heartbeat and produce a decision."""
        now = now or utcnow()
        component_id = heartbeat.component_id if heartbeat else ""
        instance_id = heartbeat.instance_id if heartbeat else ""

        if heartbeat is None:
            elapsed = (
                (now - started_at).total_seconds() if started_at is not None else 0.0
            )
            if started_at is not None and elapsed < self.startup_grace_period:
                return HeartbeatHealthDecision(
                    component_id=component_id,
                    instance_id=instance_id,
                    decision=HeartbeatDecision.STARTING,
                    elapsed=elapsed,
                    missed=False,
                    last_sequence=None,
                    last_seen=None,
                    detected_at=now,
                    reason="STARTUP_GRACE_PERIOD",
                    miss_count=miss_count,
                )
            return HeartbeatHealthDecision(
                component_id=component_id,
                instance_id=instance_id,
                decision=HeartbeatDecision.UNHEALTHY,
                elapsed=elapsed,
                missed=True,
                last_sequence=None,
                last_seen=None,
                detected_at=now,
                reason="NO_HEARTBEAT",
                miss_count=miss_count,
            )

        elapsed = (now - heartbeat.timestamp).total_seconds()

        if elapsed <= self.warning_timeout:
            decision = HeartbeatDecision.HEALTHY
            reason = "WITHIN_WARNING"
            missed = False
        elif elapsed <= self.critical_timeout:
            decision = HeartbeatDecision.DEGRADED
            reason = "WARNING_TIMEOUT"
            missed = True
        elif miss_count >= self.failure_threshold:
            decision = HeartbeatDecision.UNRESPONSIVE
            reason = "CRITICAL_TIMEOUT"
            missed = True
        else:
            decision = HeartbeatDecision.UNHEALTHY
            reason = "CRITICAL_TIMEOUT"
            missed = True

        return HeartbeatHealthDecision(
            component_id=component_id,
            instance_id=instance_id,
            decision=decision,
            elapsed=round(elapsed, 3),
            missed=missed,
            last_sequence=heartbeat.sequence,
            last_seen=heartbeat.timestamp,
            detected_at=now,
            reason=reason,
            miss_count=miss_count,
        )
