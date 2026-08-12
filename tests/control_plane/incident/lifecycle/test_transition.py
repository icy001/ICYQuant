"""IncidentTransition — auditable state-change records."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import UUID

import pytest

from services.control_plane.incident.lifecycle.state_machine import IncidentState
from services.control_plane.incident.lifecycle.transition import IncidentTransition


def _transition(**kwargs):
    return IncidentTransition(
        incident_id=kwargs.pop("incident_id", "INC-20260812-000001"),
        from_state=kwargs.pop("from_state", IncidentState.OPEN),
        to_state=kwargs.pop("to_state", IncidentState.ACKNOWLEDGED),
        actor=kwargs.pop("actor", "operator-1"),
        reason=kwargs.pop("reason", "on-call picked up"),
        **kwargs,
    )


class TestIncidentTransition:
    def test_record_carries_audit_fields(self):
        transition = _transition()
        assert transition.incident_id == "INC-20260812-000001"
        assert transition.from_state is IncidentState.OPEN
        assert transition.to_state is IncidentState.ACKNOWLEDGED
        assert transition.actor == "operator-1"
        assert transition.reason == "on-call picked up"
        assert isinstance(transition.transition_id, UUID)
        assert isinstance(transition.timestamp, datetime)
        assert transition.metadata == {}

    def test_record_is_immutable(self):
        transition = _transition()
        with pytest.raises(FrozenInstanceError):
            transition.actor = "someone-else"

    def test_metadata_is_recorded(self):
        transition = _transition(metadata={"channel": "slack", "escalation_level": 2})
        assert transition.metadata["channel"] == "slack"

    def test_serialization_roundtrip(self):
        transition = _transition(
            incident_id="INC-20260812-000042",
            metadata={"channel": "slack"},
        )
        restored = IncidentTransition.from_dict(transition.to_dict())
        assert restored == transition
        assert restored.incident_id == "INC-20260812-000042"
        assert restored.metadata == {"channel": "slack"}

    def test_to_dict_serializes_states_as_values(self):
        data = _transition().to_dict()
        assert data["from_state"] == "OPEN"
        assert data["to_state"] == "ACKNOWLEDGED"
        assert data["actor"] == "operator-1"
        assert isinstance(data["transition_id"], str)
