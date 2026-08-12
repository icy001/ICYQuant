"""IncidentPostmortem model defaults and structure."""

from __future__ import annotations

from services.control_plane.incident.postmortem.action_item import (
    RemediationActionItem,
)
from services.control_plane.incident.postmortem.impact import IncidentImpact
from services.control_plane.incident.postmortem.model import IncidentPostmortem
from services.control_plane.incident.postmortem.root_cause import (
    RootCause,
    RootCauseCategory,
)
from services.control_plane.incident.postmortem.status import PostmortemStatus

INCIDENT_ID = "INC-20260812-000001"


def test_postmortem_defaults_to_draft():
    postmortem = IncidentPostmortem(
        incident_id=INCIDENT_ID,
        title=f"Postmortem: {INCIDENT_ID}",
    )
    assert postmortem.status == PostmortemStatus.DRAFT
    assert postmortem.root_cause is None
    assert postmortem.impact is None
    assert postmortem.timeline == []
    assert postmortem.action_items == []
    assert postmortem.completed_at is None
    assert postmortem.created_at.tzinfo is not None


def test_postmortem_holds_structured_sections():
    postmortem = IncidentPostmortem(
        incident_id=INCIDENT_ID,
        title=f"Postmortem: {INCIDENT_ID}",
        root_cause=RootCause(
            category=RootCauseCategory.CONFIGURATION,
            summary="bad config",
        ),
        impact=IncidentImpact(affected_orders=3),
        action_items=[
            RemediationActionItem(
                title="fix config",
                owner="platform-team",
            )
        ],
    )
    assert postmortem.root_cause.category == RootCauseCategory.CONFIGURATION
    assert postmortem.impact.affected_orders == 3
    assert len(postmortem.action_items) == 1
