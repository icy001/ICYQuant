"""Incident audit trail (Commit 27 Part 1.4, spec sections 26-27, 40).

生产事故必须可追踪、可审计。一个完整事故的审计链:

    13:01:02  INCIDENT_CREATED
    13:01:05  STATE_CHANGED        DETECTED -> TRIAGED
    13:01:11  STATE_CHANGED        TRIAGED -> INVESTIGATING
    13:01:22  ROOT_CAUSE_IDENTIFIED
    13:01:30  CONTROL_REQUESTED    PAUSE_TRADING
    13:01:31  CONTROL_APPROVED
    13:01:31  TRADING_PAUSED
    13:02:14  RECOVERY_STARTED
    13:03:01  RECONCILIATION_PASSED
    13:03:10  STATE_CHANGED        RECOVERING -> MONITORING
    13:05:00  INCIDENT_RESOLVED
    13:10:00  INCIDENT_CLOSED

这条链以后可以直接用于 Postmortem / Audit / Compliance / Performance Review。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class IncidentAuditEvent:

    incident_id: str

    event_type: str

    timestamp: datetime

    actor: str

    previous_state: str | None

    new_state: str | None

    reason: str

    metadata: dict[str, str]


class IncidentAuditLog:
    """按 Incident 聚合的审计日志，支持时间轴回放。"""

    def __init__(self):

        self._events: list[IncidentAuditEvent] = []

    def record(
        self,
        event: IncidentAuditEvent,
    ) -> None:

        self._events.append(event)

    def events_for(
        self,
        incident_id: str,
    ) -> tuple[IncidentAuditEvent, ...]:

        return tuple(
            event
            for event in self._events
            if event.incident_id == incident_id
        )

    def timeline(
        self,
        incident_id: str,
    ) -> tuple[IncidentAuditEvent, ...]:

        return tuple(
            sorted(
                self.events_for(incident_id),
                key=lambda event: event.timestamp,
            )
        )

    def all_events(
        self,
    ) -> tuple[IncidentAuditEvent, ...]:

        return tuple(self._events)
