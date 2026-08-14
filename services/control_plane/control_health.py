"""Control Plane health: liveness, readiness, dependency health
(Commit 29 Part 1.5 §35-38).

    Liveness   - is the process alive? (only checks the process itself)
    Readiness  - can the Control Plane accept new commands?
    Dependency - per-dependency status that yields an overall DEGRADED/UNHEALTHY

Note: the spec's ``health.py`` is delivered as ``control_health.py`` because
``services/control_plane/health/`` already exists as the Commit 24 health
sub-package (same convention as execution_attempt.py / recovery_engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True)
class DependencyHealth:
    """Health of a single dependency (§38)."""

    name: str
    status: HealthStatus
    detail: str | None = None


@dataclass(frozen=True)
class HealthSnapshot:
    """Full health view (§35-38)."""

    liveness: str
    readiness: str
    dependencies: tuple[DependencyHealth, ...]

    @property
    def overall(self) -> HealthStatus:
        """DEGRADED when a non-critical dependency is down, UNHEALTHY otherwise (§38)."""
        statuses = [dependency.status for dependency in self.dependencies]
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


class DependencyProbe:
    """A named health check for one dependency (§37-38)."""

    def __init__(
        self,
        name: str,
        check: Callable[[], HealthStatus],
        *,
        critical: bool = True,
        detail: str | None = None,
    ) -> None:
        self.name = name
        self.check = check
        self.critical = critical
        self.detail = detail

    def health(self) -> DependencyHealth:
        return DependencyHealth(
            name=self.name,
            status=self.check(),
            detail=self.detail,
        )


class ControlPlaneHealth:
    """Aggregates dependency probes into liveness/readiness/overall health (§35)."""

    def __init__(self, probes: list[DependencyProbe] | None = None) -> None:
        self._probes: list[DependencyProbe] = list(probes or [])

    def register(self, probe: DependencyProbe) -> None:
        self._probes.append(probe)

    def liveness(self) -> str:
        """Only checks the process itself; never depends on external stores (§36)."""
        return "ALIVE"

    def readiness(self) -> str:
        """NOT_READY when any critical dependency is unavailable (§37)."""
        for probe in self._probes:
            if probe.critical and probe.check() is HealthStatus.UNHEALTHY:
                return "NOT_READY"
        return "READY"

    def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            liveness=self.liveness(),
            readiness=self.readiness(),
            dependencies=tuple(probe.health() for probe in self._probes),
        )
