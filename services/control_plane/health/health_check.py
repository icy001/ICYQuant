"""
HealthCheck — the *active* half of health monitoring.

Passive monitoring listens to heartbeats; active monitoring runs probes:

    Event Bus   →  Connectivity Check
    Database    →  Query Check
    Position    →  State Check

Every probe produces a :class:`HealthCheck` with PASS / WARN / FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

from .heartbeat import utcnow


class HealthCheckResult(str, Enum):
    """Outcome of a single active health check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def is_pass(self) -> bool:
        return self is HealthCheckResult.PASS

    @property
    def is_fail(self) -> bool:
        return self is HealthCheckResult.FAIL


@dataclass
class HealthCheck:
    """Result of one active health probe."""

    name: str
    component_id: str
    result: HealthCheckResult
    detail: str = ""
    checked_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "component_id": self.component_id,
            "result": self.result.value,
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }


#: A probe is any callable returning PASS/WARN/FAIL for a component.
HealthProbe = Callable[[str], HealthCheckResult]


def run_health_check(
    name: str,
    component_id: str,
    probe: HealthProbe,
    now: Optional[datetime] = None,
) -> HealthCheck:
    """Run a probe safely; exceptions are reported as FAIL."""
    now = now or utcnow()
    try:
        result = probe(component_id)
    except Exception as exc:  # noqa: BLE001 — a broken probe must never crash monitoring
        return HealthCheck(
            name=name,
            component_id=component_id,
            result=HealthCheckResult.FAIL,
            detail=f"probe raised {type(exc).__name__}: {exc}",
            checked_at=now,
        )
    return HealthCheck(
        name=name,
        component_id=component_id,
        result=result,
        checked_at=now,
    )


def run_active_checks(
    probes: List[tuple],
    component_id: str,
    now: Optional[datetime] = None,
) -> List[HealthCheck]:
    """Run several ``(name, probe)`` pairs and return all results."""
    return [
        run_health_check(name, component_id, probe, now=now) for name, probe in probes
    ]
