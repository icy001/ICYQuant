"""
IncidentMetrics — basic incident health metrics derived from the audit trail.

Spec section 16/17:

    MTTA = acknowledged_at - created_at
    MTTM = mitigation_started_at - acknowledged_at
    MTTR = resolved_at - created_at
    MTTC = closed_at - created_at

All deltas are computed from the *first* event of the relevant type, so a
metric is ``None`` until the incident actually reached that stage.  The same
events feed the Control Plane Dashboard later — no separate accounting needed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from ..audit.event import IncidentAuditEvent
from ..audit.event_type import IncidentAuditEventType


@dataclass(frozen=True)
class IncidentMetrics:

    mtta_seconds: Optional[float] = None
    mttm_seconds: Optional[float] = None
    mttr_seconds: Optional[float] = None
    mttc_seconds: Optional[float] = None

    escalation_count: int = 0
    mitigation_action_count: int = 0
    mitigation_failure_count: int = 0
    reopen_count: int = 0


class IncidentMetricsCalculator:

    def calculate(
        self,
        events: List[IncidentAuditEvent],
    ) -> IncidentMetrics:
        by_type: Dict[IncidentAuditEventType, List[IncidentAuditEvent]] = (
            defaultdict(list)
        )
        for event in events:
            by_type[event.event_type].append(event)

        def _first(
            event_type: IncidentAuditEventType,
        ) -> Optional[IncidentAuditEvent]:
            typed = by_type.get(event_type, [])
            return typed[0] if typed else None

        created = _first(IncidentAuditEventType.INCIDENT_CREATED)
        acknowledged = _first(IncidentAuditEventType.INCIDENT_ACKNOWLEDGED)
        mitigated = _first(IncidentAuditEventType.MITIGATION_STARTED)
        resolved = _first(IncidentAuditEventType.INCIDENT_RESOLVED)
        closed = _first(IncidentAuditEventType.INCIDENT_CLOSED)

        # Fall back to the first recorded event so a created_at reference is
        # always available for incidents that predate audit coverage.
        created_at = (
            created.timestamp
            if created
            else (events[0].timestamp if events else None)
        )

        def _delta(
            start: Optional[datetime],
            end: Optional[datetime],
        ) -> Optional[float]:
            if start is None or end is None:
                return None
            return (end - start).total_seconds()

        return IncidentMetrics(
            mtta_seconds=_delta(
                created_at,
                acknowledged.timestamp if acknowledged else None,
            ),
            mttm_seconds=_delta(
                acknowledged.timestamp if acknowledged else None,
                mitigated.timestamp if mitigated else None,
            ),
            mttr_seconds=_delta(
                created_at,
                resolved.timestamp if resolved else None,
            ),
            mttc_seconds=_delta(
                created_at,
                closed.timestamp if closed else None,
            ),
            escalation_count=len(
                by_type.get(IncidentAuditEventType.INCIDENT_ESCALATED, [])
            ),
            mitigation_action_count=len(
                by_type.get(IncidentAuditEventType.MITIGATION_STARTED, [])
            ),
            mitigation_failure_count=len(
                by_type.get(IncidentAuditEventType.MITIGATION_FAILED, [])
            ),
            reopen_count=len(
                by_type.get(IncidentAuditEventType.INCIDENT_REOPENED, [])
            ),
        )
