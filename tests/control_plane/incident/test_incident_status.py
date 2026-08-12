"""Unit tests: IncidentStatus lifecycle state machine."""

from __future__ import annotations

import pytest

from services.control_plane.incident.incident_status import (
    IncidentStateMachine,
    IncidentStateTransitionError,
    IncidentStatus,
)


class TestHappyPath:
    def test_full_happy_path(self):
        current = IncidentStatus.OPEN
        for target in (
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.MITIGATING,
            IncidentStatus.RESOLVED,
        ):
            assert IncidentStateMachine.can_transition(current, target)
            current = target

    def test_open_to_acknowledged(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED
        )

    def test_acknowledged_to_mitigating(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.ACKNOWLEDGED, IncidentStatus.MITIGATING
        )

    def test_mitigating_to_resolved(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.MITIGATING, IncidentStatus.RESOLVED
        )


class TestEscalationPath:
    def test_open_to_escalated(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.OPEN, IncidentStatus.ESCALATED
        )

    def test_escalated_to_mitigating(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.ESCALATED, IncidentStatus.MITIGATING
        )

    def test_escalated_to_resolved(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.ESCALATED, IncidentStatus.RESOLVED
        )

    def test_mitigating_to_escalated(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.MITIGATING, IncidentStatus.ESCALATED
        )


class TestReopenPath:
    def test_resolved_to_reopened(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.RESOLVED, IncidentStatus.REOPENED
        )

    def test_reopened_can_be_acknowledged_again(self):
        assert IncidentStateMachine.can_transition(
            IncidentStatus.REOPENED, IncidentStatus.ACKNOWLEDGED
        )


class TestInvalidTransitions:
    def test_open_cannot_reopen(self):
        assert not IncidentStateMachine.can_transition(
            IncidentStatus.OPEN, IncidentStatus.REOPENED
        )

    def test_resolved_cannot_acknowledge(self):
        assert not IncidentStateMachine.can_transition(
            IncidentStatus.RESOLVED, IncidentStatus.ACKNOWLEDGED
        )

    def test_acknowledged_cannot_reopen(self):
        assert not IncidentStateMachine.can_transition(
            IncidentStatus.ACKNOWLEDGED, IncidentStatus.REOPENED
        )

    def test_assert_transition_raises(self):
        with pytest.raises(IncidentStateTransitionError):
            IncidentStateMachine.assert_transition(
                IncidentStatus.RESOLVED, IncidentStatus.MITIGATING
            )


class TestStatusProperties:
    def test_is_open(self):
        assert IncidentStatus.OPEN.is_open
        assert IncidentStatus.ESCALATED.is_open
        assert not IncidentStatus.RESOLVED.is_open

    def test_is_resolved(self):
        assert IncidentStatus.RESOLVED.is_resolved
        assert not IncidentStatus.MITIGATING.is_resolved
