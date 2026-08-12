from __future__ import annotations

from enum import Enum


class IncidentState(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"
    REOPENED = "REOPENED"


class InvalidTransitionError(ValueError):
    pass


class IncidentStateMachine:
    _TRANSITIONS = {
        IncidentState.OPEN: {
            IncidentState.ACKNOWLEDGED,
            IncidentState.ESCALATED,
            IncidentState.RESOLVED,
        },
        IncidentState.ACKNOWLEDGED: {
            IncidentState.MITIGATING,
            IncidentState.ESCALATED,
            IncidentState.RESOLVED,
        },
        IncidentState.MITIGATING: {
            IncidentState.RESOLVED,
            IncidentState.ESCALATED,
        },
        IncidentState.ESCALATED: {
            IncidentState.ACKNOWLEDGED,
            IncidentState.MITIGATING,
            IncidentState.RESOLVED,
        },
        IncidentState.RESOLVED: {
            IncidentState.CLOSED,
            IncidentState.REOPENED,
        },
        IncidentState.REOPENED: {
            IncidentState.ACKNOWLEDGED,
            IncidentState.MITIGATING,
            IncidentState.ESCALATED,
            IncidentState.RESOLVED,
        },
        IncidentState.CLOSED: set(),
    }

    @classmethod
    def can_transition(
        cls,
        current: IncidentState,
        target: IncidentState,
    ) -> bool:
        return target in cls._TRANSITIONS.get(current, set())

    @classmethod
    def validate(
        cls,
        current: IncidentState,
        target: IncidentState,
    ) -> None:
        if not cls.can_transition(current, target):
            raise InvalidTransitionError(
                f"invalid incident transition: "
                f"{current.value} -> {target.value}"
            )
