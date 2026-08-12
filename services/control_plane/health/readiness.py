"""
Readiness — "is the component ready to accept work right now?".

Readiness checks dependencies, configuration, state and connectivity:

    Risk Engine
      ├── Position Service   ─┐
      ├── Market Data        ─┼─ any critical dependency unavailable
      ├── Risk Rules         ─┤     → Readiness = NOT_READY
      └── Event Bus          ─┘

Data freshness is a first-class readiness input: a service can be alive while
its data is stale ("Service Alive, Data Stale" → DEGRADED).

Consumer lag is another: an Event Bus consumer lagging behind is not ready to
make decisions on current data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Sequence

from .heartbeat import utcnow
from .health_status import HealthStatus


class ReadinessStatus(str, Enum):
    """Whether a component is ready to accept work."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_ready(self) -> bool:
        return self is ReadinessStatus.READY


class DataFreshness(str, Enum):
    """Freshness classification of a component's data."""

    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


@dataclass
class FreshnessPolicy:
    """Per-component data freshness thresholds (seconds since last update)."""

    component_id: str
    fresh_seconds: float = 5.0
    stale_seconds: float = 15.0

    def evaluate(
        self,
        last_update: Optional[datetime],
        now: Optional[datetime] = None,
    ) -> DataFreshness:
        """Classify data freshness: FRESH / STALE / EXPIRED / UNKNOWN."""
        if last_update is None:
            return DataFreshness.UNKNOWN
        now = now or utcnow()
        age = (now - last_update).total_seconds()
        if age <= self.fresh_seconds:
            return DataFreshness.FRESH
        if age <= self.stale_seconds:
            return DataFreshness.STALE
        return DataFreshness.EXPIRED


@dataclass
class DependencyStatus:
    """Health of a single dependency as seen by the dependant component."""

    component_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    detail: str = ""


@dataclass
class ReadinessEvaluation:
    """Result of evaluating a component's readiness."""

    component_id: str
    status: ReadinessStatus
    reasons: List[str] = field(default_factory=list)
    dependencies: List[DependencyStatus] = field(default_factory=list)
    freshness: DataFreshness = DataFreshness.UNKNOWN
    consumer_lag: Optional[int] = None
    evaluated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "dependencies": [
                {"component_id": d.component_id, "status": d.status.value, "detail": d.detail}
                for d in self.dependencies
            ],
            "freshness": self.freshness.value,
            "consumer_lag": self.consumer_lag,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


def evaluate_readiness(
    component_id: str,
    dependencies: Optional[Sequence[DependencyStatus]] = None,
    freshness: DataFreshness = DataFreshness.UNKNOWN,
    consumer_lag: Optional[int] = None,
    consumer_lag_warning: Optional[int] = None,
    consumer_lag_critical: Optional[int] = None,
    now: Optional[datetime] = None,
) -> ReadinessEvaluation:
    """Compute a component's readiness from its dependency/data inputs.

    Rules (worst wins):

    * any dependency UNHEALTHY or DEGRADED        → NOT_READY
    * data EXPIRED                                → FAILED
    * data STALE                                  → NOT_READY
    * consumer lag > critical threshold           → FAILED
    * consumer lag > warning threshold            → NOT_READY
    * otherwise                                   → READY
    """
    now = now or utcnow()
    dependencies = list(dependencies or [])
    reasons: List[str] = []
    status = ReadinessStatus.READY

    if any(d.status is HealthStatus.UNHEALTHY for d in dependencies):
        status = ReadinessStatus.NOT_READY
        reasons.append("DEPENDENCY_UNHEALTHY")
    elif any(d.status is HealthStatus.DEGRADED for d in dependencies):
        status = ReadinessStatus.NOT_READY
        reasons.append("DEPENDENCY_DEGRADED")

    if freshness is DataFreshness.EXPIRED:
        status = ReadinessStatus.FAILED
        reasons.append("DATA_EXPIRED")
    elif freshness is DataFreshness.STALE:
        status = _worse_readiness(status, ReadinessStatus.NOT_READY)
        reasons.append("DATA_STALE")

    if consumer_lag is not None and consumer_lag_critical is not None:
        if consumer_lag > consumer_lag_critical:
            status = ReadinessStatus.FAILED
            reasons.append("CONSUMER_LAG_CRITICAL")
    if consumer_lag is not None and consumer_lag_warning is not None:
        if consumer_lag > consumer_lag_warning:
            status = _worse_readiness(status, ReadinessStatus.NOT_READY)
            reasons.append("CONSUMER_LAG_HIGH")

    return ReadinessEvaluation(
        component_id=component_id,
        status=status,
        reasons=reasons,
        dependencies=dependencies,
        freshness=freshness,
        consumer_lag=consumer_lag,
        evaluated_at=now,
    )


_READINESS_RANK = {
    ReadinessStatus.READY: 0,
    ReadinessStatus.NOT_READY: 1,
    ReadinessStatus.FAILED: 2,
    ReadinessStatus.UNKNOWN: 0,
}


def _worse_readiness(a: ReadinessStatus, b: ReadinessStatus) -> ReadinessStatus:
    if a is ReadinessStatus.UNKNOWN:
        return b
    if b is ReadinessStatus.UNKNOWN:
        return a
    return a if _READINESS_RANK[a] >= _READINESS_RANK[b] else b
