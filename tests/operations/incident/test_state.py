"""Incident state machine tests (Commit 27 Part 1.4, spec sections 28-29, 35-36)."""

from __future__ import annotations

import pytest

from services.operations import (
    VALID_TRANSITIONS,
    IncidentState,
    transition,
)

FULL_LIFECYCLE = (
    IncidentState.TRIAGED,
    IncidentState.INVESTIGATING,
    IncidentState.MITIGATING,
    IncidentState.RECOVERING,
    IncidentState.MONITORING,
    IncidentState.RESOLVED,
    IncidentState.CLOSED,
)


def test_incident_transition(incident):
    # spec section 35
    previous = transition(
        incident,
        IncidentState.TRIAGED,
    )

    assert previous is IncidentState.DETECTED
    assert incident.state is IncidentState.TRIAGED


def test_transition_returns_previous_state(incident):

    previous = transition(
        incident,
        IncidentState.TRIAGED,
    )

    assert previous is IncidentState.DETECTED


def test_invalid_transition_rejected(incident):
    # spec section 36
    with pytest.raises(ValueError):

        transition(
            incident,
            IncidentState.RESOLVED,
        )


def test_detected_cannot_skip_to_resolved(incident):

    with pytest.raises(ValueError):

        transition(
            incident,
            IncidentState.RESOLVED,
        )


def test_invalid_transition_does_not_mutate_state(incident):

    with pytest.raises(ValueError):

        transition(
            incident,
            IncidentState.MONITORING,
        )

    assert incident.state is IncidentState.DETECTED


def test_full_lifecycle(incident):

    for target in FULL_LIFECYCLE:
        transition(incident, target)

    assert incident.state is IncidentState.CLOSED


def test_closed_is_terminal(incident):

    for target in FULL_LIFECYCLE:
        transition(incident, target)

    with pytest.raises(ValueError):

        transition(
            incident,
            IncidentState.INVESTIGATING,
        )


def test_triaged_can_go_to_mitigating_directly(incident):

    transition(incident, IncidentState.TRIAGED)
    transition(incident, IncidentState.MITIGATING)

    assert incident.state is IncidentState.MITIGATING


def test_valid_transitions_table_shape():

    assert IncidentState.DETECTED in VALID_TRANSITIONS
    assert IncidentState.CLOSED in VALID_TRANSITIONS
    assert VALID_TRANSITIONS[IncidentState.CLOSED] == set()

    assert IncidentState.TRIAGED in (
        VALID_TRANSITIONS[IncidentState.DETECTED]
    )
    assert IncidentState.MITIGATING in (
        VALID_TRANSITIONS[IncidentState.TRIAGED]
    )
    assert IncidentState.INVESTIGATING in (
        VALID_TRANSITIONS[IncidentState.TRIAGED]
    )
