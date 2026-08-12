"""Postmortem service: creation, completion gate, reopen visibility, metrics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.incident.audit.event import IncidentAuditEvent
from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService
from services.control_plane.incident.postmortem.action_item import (
    RemediationActionItem,
)
from services.control_plane.incident.postmortem.impact import IncidentImpact
from services.control_plane.incident.postmortem.metrics import (
    IncidentMetricsCalculator,
)
from services.control_plane.incident.postmortem.root_cause import (
    RootCause,
    RootCauseCategory,
)
from services.control_plane.incident.postmortem.service import (
    IncidentPostmortemService,
)
from services.control_plane.incident.postmortem.status import PostmortemStatus

INCIDENT_ID = "INC-20260812-000001"


@pytest.fixture
def audit_service():
    repository = InMemoryIncidentAuditRepository()
    recorder = IncidentAuditRecorder(repository)
    return IncidentAuditService(recorder)


@pytest.fixture
def postmortem_service(audit_service):
    return IncidentPostmortemService(audit_service)


def _fill_completion_fields(postmortem):
    postmortem.root_cause = RootCause(
        category=RootCauseCategory.CODE,
        summary="missing null guard",
    )
    postmortem.impact = IncidentImpact(affected_orders=4)
    postmortem.action_items.append(
        RemediationActionItem(
            title="add null guard",
            owner="execution-team",
        )
    )
    return postmortem


def test_postmortem_requires_root_cause(postmortem_service, incident_factory):
    postmortem = postmortem_service.create(incident_factory())
    postmortem.impact = IncidentImpact()
    postmortem.action_items.append(
        RemediationActionItem(title="x", owner="y")
    )
    with pytest.raises(ValueError, match="root cause"):
        postmortem_service.complete(postmortem)


def test_postmortem_requires_impact(postmortem_service, incident_factory):
    postmortem = postmortem_service.create(incident_factory())
    postmortem.root_cause = RootCause(
        category=RootCauseCategory.CODE,
        summary="missing null guard",
    )
    postmortem.action_items.append(
        RemediationActionItem(title="x", owner="y")
    )
    with pytest.raises(ValueError, match="impact"):
        postmortem_service.complete(postmortem)


def test_postmortem_requires_remediation(postmortem_service, incident_factory):
    postmortem = postmortem_service.create(incident_factory())
    postmortem.root_cause = RootCause(
        category=RootCauseCategory.CODE,
        summary="missing null guard",
    )
    postmortem.impact = IncidentImpact()
    with pytest.raises(ValueError, match="remediation action"):
        postmortem_service.complete(postmortem)


def test_postmortem_can_be_completed(postmortem_service, incident_factory):
    postmortem = _fill_completion_fields(
        postmortem_service.create(incident_factory())
    )
    postmortem_service.complete(postmortem)
    assert postmortem.status == PostmortemStatus.COMPLETED
    assert postmortem.completed_at is not None


def test_postmortem_flow_states(postmortem_service, incident_factory):
    postmortem = postmortem_service.create(incident_factory())
    postmortem_service.start_review(postmortem)
    assert postmortem.status == PostmortemStatus.IN_REVIEW
    postmortem_service.approve(postmortem)
    assert postmortem.status == PostmortemStatus.APPROVED


def test_create_builds_timeline_from_audit(
    audit_service,
    postmortem_service,
    incident_factory,
):
    incident = incident_factory()
    audit_service.record(
        incident.id,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
        payload={"description": "detected"},
    )
    postmortem = postmortem_service.create(incident)
    assert len(postmortem.timeline) == 1
    assert postmortem.timeline[0].description == "detected"
    assert postmortem.title == f"Postmortem: {incident.id}"


def test_reopened_incident_appears_in_postmortem(
    audit_service,
    postmortem_service,
    incident_factory,
):
    incident = incident_factory()
    for event_type, actor in [
        (IncidentAuditEventType.INCIDENT_CREATED, "system"),
        (IncidentAuditEventType.INCIDENT_ACKNOWLEDGED, "operator-1"),
        (IncidentAuditEventType.INCIDENT_RESOLVED, "operator-1"),
        (IncidentAuditEventType.INCIDENT_REOPENED, "operator-1"),
    ]:
        audit_service.record(incident.id, event_type, actor=actor)

    postmortem = postmortem_service.create(incident)
    event_types = [entry.event_type for entry in postmortem.timeline]
    assert "INCIDENT_REOPENED" in event_types
    assert event_types.index("INCIDENT_CREATED") < event_types.index(
        "INCIDENT_REOPENED"
    )


def test_metrics_from_audit_events():
    t0 = datetime(2026, 8, 12, 9, 31, 2, tzinfo=timezone.utc)
    events = [
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_CREATED,
            "system",
            timestamp=t0,
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_ESCALATED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=2),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=5),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.MITIGATION_STARTED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=20),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.MITIGATION_FAILED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=30),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.MITIGATION_STARTED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=40),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_RESOLVED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=60),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_REOPENED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=80),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_RESOLVED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=120),
        ),
        IncidentAuditEvent(
            INCIDENT_ID,
            IncidentAuditEventType.INCIDENT_CLOSED,
            "operator-1",
            timestamp=t0 + timedelta(seconds=300),
        ),
    ]
    metrics = IncidentMetricsCalculator().calculate(events)
    assert metrics.mtta_seconds == 5
    assert metrics.mttm_seconds == 15
    assert metrics.mttr_seconds == 60
    assert metrics.mttc_seconds == 300
    assert metrics.escalation_count == 1
    assert metrics.mitigation_action_count == 2
    assert metrics.mitigation_failure_count == 1
    assert metrics.reopen_count == 1


def test_service_metrics_via_audit(
    audit_service,
    postmortem_service,
    incident_factory,
):
    incident = incident_factory()
    audit_service.record(
        incident.id,
        IncidentAuditEventType.INCIDENT_CREATED,
        actor="system",
    )
    audit_service.record(
        incident.id,
        IncidentAuditEventType.INCIDENT_ACKNOWLEDGED,
        actor="operator-1",
    )
    metrics = postmortem_service.metrics(incident.id)
    assert metrics.mtta_seconds is not None
    assert metrics.mttr_seconds is None
    assert metrics.reopen_count == 0
