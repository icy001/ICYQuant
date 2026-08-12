"""
HealthEvaluator — turns monitoring signals into a HealthStatus + HealthScore.

Inputs:

    Liveness  +  Readiness  +  Heartbeat  +  Dependencies (+ active checks)

Output:

    HealthStatus   (UNKNOWN / HEALTHY / DEGRADED / UNHEALTHY)
    health_score   (0..100, weighted observation, NOT a trading gate)

State matrix (exact):

    | Liveness | Readiness | Health    |
    | ALIVE    | READY     | HEALTHY   |
    | ALIVE    | NOT_READY | DEGRADED  |
    | ALIVE    | FAILED    | UNHEALTHY |
    | DEAD     | any       | UNHEALTHY |
    | UNKNOWN  | UNKNOWN   | UNKNOWN   |

Weighted score:

    Heartbeat 30%  Liveness 25%  Readiness 25%  Dependencies 20%

Health score is an *observation* — a 95-score Risk Engine with NOT_READY
readiness must still keep the trading gate DENY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from ..domain.component_registry import ComponentCriticality
from .health_check import HealthCheck, HealthCheckResult
from .health_status import HealthStatus
from .heartbeat import Heartbeat, HeartbeatStatus, utcnow
from .liveness import LivenessStatus
from .readiness import DependencyStatus, ReadinessStatus

# Weights — must sum to 1.0 (spec: 30 / 25 / 25 / 20).
WEIGHT_HEARTBEAT = 0.30
WEIGHT_LIVENESS = 0.25
WEIGHT_READINESS = 0.25
WEIGHT_DEPENDENCIES = 0.20


@dataclass
class HealthEvaluation:
    """Full result of evaluating one component's health."""

    component_id: str
    status: HealthStatus
    score: float
    liveness: LivenessStatus
    readiness: ReadinessStatus
    heartbeat_status: HeartbeatStatus
    dependencies: List[DependencyStatus]
    checks: List[HealthCheck]
    reasons: List[str]
    criticality: Optional[ComponentCriticality] = None
    evaluated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "score": self.score,
            "liveness": self.liveness.value,
            "readiness": self.readiness.value,
            "heartbeat_status": self.heartbeat_status.value,
            "dependencies": [
                {"component_id": d.component_id, "status": d.status.value}
                for d in self.dependencies
            ],
            "checks": [c.to_dict() for c in self.checks],
            "reasons": list(self.reasons),
            "criticality": self.criticality.value if self.criticality else None,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class HealthEvaluator:
    """Pure evaluation of health from liveness / readiness / heartbeat / deps."""

    def evaluate(
        self,
        component_id: str,
        liveness: LivenessStatus = LivenessStatus.UNKNOWN,
        readiness: ReadinessStatus = ReadinessStatus.UNKNOWN,
        heartbeat: Optional[Heartbeat] = None,
        heartbeat_age: Optional[float] = None,
        heartbeat_status: Optional[HeartbeatStatus] = None,
        dependencies: Optional[Sequence[DependencyStatus]] = None,
        checks: Optional[Sequence[HealthCheck]] = None,
        warning_timeout: float = 10.0,
        critical_timeout: float = 15.0,
        criticality: Optional[ComponentCriticality] = None,
        now: Optional[datetime] = None,
    ) -> HealthEvaluation:
        """Evaluate component health and produce status + weighted score."""
        now = now or utcnow()
        dependencies = list(dependencies or [])
        checks = list(checks or [])
        if isinstance(heartbeat_status, str):
            heartbeat_status = HeartbeatStatus(heartbeat_status)
        reasons: List[str] = []

        status = self._matrix_status(liveness, readiness, reasons)

        # Heartbeat timeout overrides the matrix downward (never upward).
        hb_floor = self._heartbeat_floor(
            heartbeat, heartbeat_age, heartbeat_status,
            warning_timeout, critical_timeout, reasons,
        )
        if hb_floor is not None and _rank(hb_floor) > _rank(status):
            status = hb_floor

        # Dependency degradation. A sick dependency makes this component
        # DEGRADED (readiness NOT_READY) — it does not by itself kill the
        # component's own health (spec: Position UNHEALTHY → Risk DEGRADED).
        if any(d.status is HealthStatus.UNHEALTHY for d in dependencies):
            status = _worse(status, HealthStatus.DEGRADED)
            reasons.append("DEPENDENCY_UNHEALTHY")
        elif any(
            d.status is HealthStatus.DEGRADED for d in dependencies
        ):
            status = _worse(status, HealthStatus.DEGRADED)
            reasons.append("DEPENDENCY_DEGRADED")

        # Active checks override the status.
        if any(c.result is HealthCheckResult.FAIL for c in checks):
            status = _worse(status, HealthStatus.UNHEALTHY)
            reasons.append("HEALTH_CHECK_FAIL")
        elif any(c.result is HealthCheckResult.WARN for c in checks):
            status = _worse(status, HealthStatus.DEGRADED)
            reasons.append("HEALTH_CHECK_WARN")

        score = self.score(
            heartbeat_age=heartbeat_age,
            heartbeat_status=heartbeat_status,
            liveness=liveness,
            readiness=readiness,
            dependencies=dependencies,
        )

        return HealthEvaluation(
            component_id=component_id,
            status=status,
            score=round(score, 1),
            liveness=liveness,
            readiness=readiness,
            heartbeat_status=heartbeat_status or (
                heartbeat.status if heartbeat else HeartbeatStatus.UNKNOWN
            ),
            dependencies=dependencies,
            checks=checks,
            reasons=reasons,
            criticality=criticality,
            evaluated_at=now,
        )

    # ------------------------------------------------------------------ #

    @staticmethod
    def score(
        heartbeat_age: Optional[float] = None,
        heartbeat_status: Optional[HeartbeatStatus] = None,
        liveness: LivenessStatus = LivenessStatus.UNKNOWN,
        readiness: ReadinessStatus = ReadinessStatus.UNKNOWN,
        dependencies: Optional[Sequence[DependencyStatus]] = None,
        warning_timeout: float = 10.0,
        critical_timeout: float = 15.0,
    ) -> float:
        """Weighted health score in [0, 100] (observation, not a gate)."""
        dependencies = list(dependencies or [])

        hb_score = 100.0
        if heartbeat_age is not None:
            if heartbeat_age <= warning_timeout:
                hb_score = 100.0
            elif heartbeat_age <= critical_timeout:
                t = (critical_timeout - heartbeat_age) / (
                    critical_timeout - warning_timeout
                )
                hb_score = 40.0 + 60.0 * t
            else:
                hb_score = 0.0
        elif heartbeat_status is HeartbeatStatus.HEALTHY:
            hb_score = 100.0
        elif heartbeat_status is HeartbeatStatus.DEGRADED:
            hb_score = 60.0
        elif heartbeat_status in (HeartbeatStatus.UNHEALTHY, HeartbeatStatus.UNKNOWN):
            hb_score = 0.0
        else:
            hb_score = 0.0

        liveness_score = {
            LivenessStatus.ALIVE: 100.0,
            LivenessStatus.UNKNOWN: 50.0,
            LivenessStatus.DEAD: 0.0,
        }[liveness]

        readiness_score = {
            ReadinessStatus.READY: 100.0,
            ReadinessStatus.NOT_READY: 60.0,
            ReadinessStatus.FAILED: 0.0,
            ReadinessStatus.UNKNOWN: 50.0,
        }[readiness]

        if dependencies:
            dep_score = 100.0 * sum(
                1.0 for d in dependencies if d.status is HealthStatus.HEALTHY
            ) / len(dependencies)
        else:
            dep_score = 100.0

        return (
            WEIGHT_HEARTBEAT * hb_score
            + WEIGHT_LIVENESS * liveness_score
            + WEIGHT_READINESS * readiness_score
            + WEIGHT_DEPENDENCIES * dep_score
        )

    # ------------------------------------------------------------------ #

    @staticmethod
    def _matrix_status(
        liveness: LivenessStatus,
        readiness: ReadinessStatus,
        reasons: List[str],
    ) -> HealthStatus:
        if liveness is LivenessStatus.DEAD:
            reasons.append("LIVENESS_DEAD")
            return HealthStatus.UNHEALTHY
        if liveness is LivenessStatus.UNKNOWN:
            reasons.append("LIVENESS_UNKNOWN")
            return HealthStatus.UNKNOWN
        if readiness is ReadinessStatus.READY:
            return HealthStatus.HEALTHY
        if readiness is ReadinessStatus.NOT_READY:
            reasons.append("READINESS_NOT_READY")
            return HealthStatus.DEGRADED
        if readiness is ReadinessStatus.FAILED:
            reasons.append("READINESS_FAILED")
            return HealthStatus.UNHEALTHY
        reasons.append("READINESS_UNKNOWN")
        return HealthStatus.UNKNOWN

    @staticmethod
    def _heartbeat_floor(
        heartbeat: Optional[Heartbeat],
        heartbeat_age: Optional[float],
        heartbeat_status: Optional[HeartbeatStatus],
        warning_timeout: float,
        critical_timeout: float,
        reasons: List[str],
    ) -> Optional[HealthStatus]:
        if heartbeat_age is not None:
            if heartbeat_age > critical_timeout:
                reasons.append("HEARTBEAT_CRITICAL_TIMEOUT")
                return HealthStatus.UNHEALTHY
            if heartbeat_age > warning_timeout:
                reasons.append("HEARTBEAT_WARNING_TIMEOUT")
                return HealthStatus.DEGRADED
        if heartbeat is not None and heartbeat_age is None:
            if heartbeat.status is HeartbeatStatus.UNHEALTHY:
                reasons.append("HEARTBEAT_UNHEALTHY")
                return HealthStatus.UNHEALTHY
            if heartbeat.status is HeartbeatStatus.DEGRADED:
                reasons.append("HEARTBEAT_DEGRADED")
                return HealthStatus.DEGRADED
        if heartbeat_status is HeartbeatStatus.UNHEALTHY:
            reasons.append("HEARTBEAT_UNHEALTHY")
            return HealthStatus.UNHEALTHY
        if heartbeat_status is HeartbeatStatus.DEGRADED:
            reasons.append("HEARTBEAT_DEGRADED")
            return HealthStatus.DEGRADED
        return None


def _rank(status: HealthStatus) -> int:
    return {
        HealthStatus.HEALTHY: 0,
        HealthStatus.DEGRADED: 1,
        HealthStatus.UNHEALTHY: 2,
        HealthStatus.UNKNOWN: -1,
    }[status]


def _worse(a: HealthStatus, b: HealthStatus) -> HealthStatus:
    if a is HealthStatus.UNKNOWN:
        return b
    if b is HealthStatus.UNKNOWN:
        return a
    return a if _rank(a) >= _rank(b) else b
