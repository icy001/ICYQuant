"""
HealthStatus — the overall health classification of a component.

Health is the top of the three-layer model:

    Health
      ├── Liveness   ("is the process alive?")
      └── Readiness  ("is it ready to do work?")

The status is produced by :class:`HealthEvaluator` from liveness, readiness,
heartbeat and dependency signals and must never be interpreted by monitors
themselves — monitors emit events, the Control Plane decides.
"""

from __future__ import annotations

from enum import Enum
from typing import List


class HealthStatus(str, Enum):
    """Overall component health classification."""

    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"

    @property
    def is_healthy(self) -> bool:
        return self is HealthStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """A component that can still (partially) participate in the system."""
        return self in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    @property
    def is_terminal_failure(self) -> bool:
        return self is HealthStatus.UNHEALTHY


# Rank used to pick the *worst* known status when combining signals.
# UNKNOWN is excluded: it means "no information" and must not drag a
# confirmed signal back to UNKNOWN (matrix rows in the spec stay exact).
_SEVERITY = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.UNHEALTHY: 2,
}


def worse_status(a: HealthStatus, b: HealthStatus) -> HealthStatus:
    """Return the more severe of two known statuses.

    ``UNKNOWN`` is treated as "no information" and is only returned when both
    inputs are unknown.
    """
    if a is HealthStatus.UNKNOWN:
        return b
    if b is HealthStatus.UNKNOWN:
        return a
    return a if _SEVERITY[a] >= _SEVERITY[b] else b


def combine_statuses(statuses: List[HealthStatus]) -> HealthStatus:
    """Combine several status signals into one, keeping the worst known one.

    ``UNKNOWN`` inputs are ignored; if everything is unknown the result is
    ``UNKNOWN``.
    """
    known = [s for s in statuses if s is not HealthStatus.UNKNOWN]
    if not known:
        return HealthStatus.UNKNOWN
    worst = known[0]
    for s in known[1:]:
        worst = worse_status(worst, s)
    return worst
