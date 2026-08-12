from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from ..incident import Incident
from .errors import ActorRequiredError, ReasonRequiredError
from .state_machine import (
    IncidentState,
    IncidentStateMachine,
)
from .transition import IncidentTransition


@dataclass
class LifecycleResult:
    incident: Incident
    transition: IncidentTransition


class IncidentLifecycleService:

    def transition(
        self,
        incident: Incident,
        target: IncidentState,
        *,
        actor: str,
        reason: str,
        metadata: dict | None = None,
    ) -> LifecycleResult:

        current = IncidentState(incident.state.value)

        IncidentStateMachine.validate(
            current,
            target,
        )

        if not actor or not actor.strip():
            raise ActorRequiredError("actor is required for a lifecycle transition")
        if not reason or not reason.strip():
            raise ReasonRequiredError("reason is required for a lifecycle transition")

        transition = IncidentTransition(
            incident_id=incident.id,
            from_state=current,
            to_state=target,
            actor=actor,
            reason=reason,
            metadata=metadata or {},
        )

        incident.state = target
        incident.updated_at = datetime.now(timezone.utc)

        incident.transitions.append(transition)

        return LifecycleResult(
            incident=incident,
            transition=transition,
        )

    def acknowledge(
        self,
        incident: Incident,
        *,
        actor: str,
        reason: str = "incident acknowledged",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.ACKNOWLEDGED,
            actor=actor,
            reason=reason,
        )

    def start_mitigation(
        self,
        incident: Incident,
        *,
        actor: str,
        reason: str = "mitigation started",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.MITIGATING,
            actor=actor,
            reason=reason,
        )

    def resolve(
        self,
        incident: Incident,
        *,
        actor: str,
        reason: str = "incident resolved",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.RESOLVED,
            actor=actor,
            reason=reason,
        )

    def close(
        self,
        incident: Incident,
        *,
        actor: str = "system",
        reason: str = "resolution verified",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.CLOSED,
            actor=actor,
            reason=reason,
        )

    def reopen(
        self,
        incident: Incident,
        *,
        actor: str = "system",
        reason: str = "incident condition detected again",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.REOPENED,
            actor=actor,
            reason=reason,
        )

    def escalate(
        self,
        incident: Incident,
        *,
        actor: str = "system",
        reason: str = "lifecycle timeout",
    ) -> LifecycleResult:

        return self.transition(
            incident,
            IncidentState.ESCALATED,
            actor=actor,
            reason=reason,
        )
