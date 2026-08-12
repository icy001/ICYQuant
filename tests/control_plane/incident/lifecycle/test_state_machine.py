import pytest

from services.control_plane.incident.lifecycle.state_machine import (
    IncidentState,
    IncidentStateMachine,
    InvalidTransitionError,
)


def test_open_to_acknowledged():
    assert IncidentStateMachine.can_transition(
        IncidentState.OPEN,
        IncidentState.ACKNOWLEDGED,
    )


def test_acknowledged_to_mitigating():
    assert IncidentStateMachine.can_transition(
        IncidentState.ACKNOWLEDGED,
        IncidentState.MITIGATING,
    )


def test_mitigating_to_resolved():
    assert IncidentStateMachine.can_transition(
        IncidentState.MITIGATING,
        IncidentState.RESOLVED,
    )


def test_resolved_to_closed():
    assert IncidentStateMachine.can_transition(
        IncidentState.RESOLVED,
        IncidentState.CLOSED,
    )


def test_resolved_to_reopened():
    assert IncidentStateMachine.can_transition(
        IncidentState.RESOLVED,
        IncidentState.REOPENED,
    )


def test_closed_is_terminal():
    assert not IncidentStateMachine.can_transition(
        IncidentState.CLOSED,
        IncidentState.OPEN,
    )


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransitionError):
        IncidentStateMachine.validate(
            IncidentState.CLOSED,
            IncidentState.OPEN,
        )
