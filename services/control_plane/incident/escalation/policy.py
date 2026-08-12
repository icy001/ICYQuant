from __future__ import annotations

from dataclasses import dataclass

from ..incident_severity import IncidentSeverity
from .level import EscalationLevel


@dataclass(frozen=True)
class EscalationPolicy:
    initial_level: EscalationLevel
    max_level: EscalationLevel
    timeout_seconds: tuple[int, ...]


DEFAULT_ESCALATION_POLICIES = {
    IncidentSeverity.LOW: EscalationPolicy(
        initial_level=EscalationLevel.L1,
        max_level=EscalationLevel.L2,
        timeout_seconds=(1800,),
    ),
    IncidentSeverity.MEDIUM: EscalationPolicy(
        initial_level=EscalationLevel.L1,
        max_level=EscalationLevel.L3,
        timeout_seconds=(900, 1800),
    ),
    IncidentSeverity.HIGH: EscalationPolicy(
        initial_level=EscalationLevel.L2,
        max_level=EscalationLevel.L4,
        timeout_seconds=(300, 900),
    ),
    IncidentSeverity.CRITICAL: EscalationPolicy(
        initial_level=EscalationLevel.L3,
        max_level=EscalationLevel.L4,
        timeout_seconds=(60,),
    ),
}
