from __future__ import annotations

from dataclasses import dataclass

from ..incident_severity import IncidentSeverity


@dataclass(frozen=True)
class LifecyclePolicy:
    acknowledge_timeout_seconds: int
    mitigation_timeout_seconds: int
    resolution_timeout_seconds: int
    auto_escalate: bool = True


DEFAULT_POLICIES = {
    IncidentSeverity.LOW: LifecyclePolicy(
        acknowledge_timeout_seconds=900,
        mitigation_timeout_seconds=3600,
        resolution_timeout_seconds=14400,
    ),
    IncidentSeverity.MEDIUM: LifecyclePolicy(
        acknowledge_timeout_seconds=600,
        mitigation_timeout_seconds=1800,
        resolution_timeout_seconds=7200,
    ),
    IncidentSeverity.HIGH: LifecyclePolicy(
        acknowledge_timeout_seconds=300,
        mitigation_timeout_seconds=900,
        resolution_timeout_seconds=3600,
    ),
    IncidentSeverity.CRITICAL: LifecyclePolicy(
        acknowledge_timeout_seconds=60,
        mitigation_timeout_seconds=300,
        resolution_timeout_seconds=900,
    ),
}


def get_policy(severity: IncidentSeverity) -> LifecyclePolicy:
    return DEFAULT_POLICIES[severity]
