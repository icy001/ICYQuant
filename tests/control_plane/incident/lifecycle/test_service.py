"""IncidentLifecycleService — audited lifecycle transitions."""
from __future__ import annotations

import pytest

from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.lifecycle.errors import (
    ActorRequiredError,
    ReasonRequiredError,
)
from services.control_plane.incident.lifecycle.service import (
    IncidentLifecycleService,
)
from services.control_plane.incident.lifecycle.state_machine import (
    IncidentState,
    InvalidTransitionError,
)


class TestLifecycleService:
    def test_acknowledge_records_transition(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        result = service.acknowledge(incident, actor="operator-1")

        assert incident.state is IncidentStatus.ACKNOWLEDGED
        assert len(incident.transitions) == 1
        transition = result.transition
        assert incident.transitions[0] is transition
        assert transition.from_state is IncidentState.OPEN
        assert transition.to_state is IncidentState.ACKNOWLEDGED
        assert transition.actor == "operator-1"

    def test_full_happy_path(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        service.acknowledge(incident, actor="operator-1")
        service.start_mitigation(incident, actor="operator-1")
        service.resolve(incident, actor="operator-1")
        service.close(incident)

        assert incident.state is IncidentStatus.CLOSED
        assert [t.to_state for t in incident.transitions] == [
            IncidentState.ACKNOWLEDGED,
            IncidentState.MITIGATING,
            IncidentState.RESOLVED,
            IncidentState.CLOSED,
        ]

    def test_resolve_then_reopen_keeps_same_incident(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        service.acknowledge(incident, actor="operator-1")
        service.start_mitigation(incident, actor="operator-1")
        service.resolve(incident, actor="operator-1")
        # verification fails / condition active again -> reopen, not a new incident
        service.reopen(incident)

        assert incident.state is IncidentStatus.REOPENED
        assert incident.reopen_count == 0  # lifecycle layer keeps its own audit
        assert len(incident.transitions) == 4

    def test_escalate_via_service(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        result = service.escalate(incident, actor="system", reason="lifecycle timeout")

        assert incident.state is IncidentStatus.ESCALATED
        assert result.transition.to_state is IncidentState.ESCALATED

    def test_invalid_transition_raises(self, incident_factory):
        incident = incident_factory(state="CLOSED")
        service = IncidentLifecycleService()
        with pytest.raises(InvalidTransitionError):
            service.acknowledge(incident, actor="operator-1")

    def test_actor_is_required(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        with pytest.raises(ActorRequiredError):
            service.acknowledge(incident, actor="")

    def test_reason_is_required(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        with pytest.raises(ReasonRequiredError):
            service.transition(
                incident,
                IncidentState.ACKNOWLEDGED,
                actor="operator-1",
                reason="  ",
            )

    def test_metadata_is_recorded(self, incident_factory):
        incident = incident_factory()
        service = IncidentLifecycleService()
        result = service.transition(
            incident,
            IncidentState.ACKNOWLEDGED,
            actor="operator-1",
            reason="pager picked up",
            metadata={"channel": "slack"},
        )
        assert result.transition.metadata == {"channel": "slack"}
