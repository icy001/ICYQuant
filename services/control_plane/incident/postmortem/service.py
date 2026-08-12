"""
IncidentPostmortemService — build and drive postmortems to completion.

The postmortem timeline is rebuilt from the audit trail (never hand-typed),
and completion is gated: without a root cause, an impact assessment and at
least one remediation action item the postmortem cannot be completed
(spec sections 14/20).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .metrics import IncidentMetrics, IncidentMetricsCalculator
from .model import IncidentPostmortem
from .status import PostmortemStatus
from .timeline import IncidentTimelineBuilder


class IncidentPostmortemService:

    def __init__(self, audit_service) -> None:
        self.audit_service = audit_service
        self.timeline_builder = IncidentTimelineBuilder()
        self.metrics_calculator = IncidentMetricsCalculator()

    def create(
        self,
        incident,
        *,
        title: Optional[str] = None,
    ) -> IncidentPostmortem:
        """Create a DRAFT postmortem with a timeline auto-built from audit."""
        events = self.audit_service.timeline(incident.id)
        timeline = self.timeline_builder.build(events)

        return IncidentPostmortem(
            incident_id=incident.id,
            title=title or f"Postmortem: {incident.id}",
            timeline=timeline,
        )

    def start_review(self, postmortem: IncidentPostmortem) -> None:
        postmortem.status = PostmortemStatus.IN_REVIEW

    def approve(self, postmortem: IncidentPostmortem) -> None:
        postmortem.status = PostmortemStatus.APPROVED

    def complete(self, postmortem: IncidentPostmortem) -> None:
        """Complete the postmortem — enforced completion gate.

        Root cause, impact assessment and at least one remediation action item
        are mandatory (spec section 20).
        """
        if not postmortem.root_cause:
            raise ValueError("root cause is required")

        if postmortem.impact is None:
            raise ValueError("impact assessment is required")

        if not postmortem.action_items:
            raise ValueError("at least one remediation action is required")

        postmortem.status = PostmortemStatus.COMPLETED
        postmortem.completed_at = datetime.now(timezone.utc)

    def metrics(self, incident_id: str) -> IncidentMetrics:
        """Derive MTTA/MTTM/MTTR/MTTC and counts from the audit trail."""
        events = self.audit_service.timeline(incident_id)
        return self.metrics_calculator.calculate(events)
