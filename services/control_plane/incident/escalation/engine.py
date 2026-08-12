from __future__ import annotations

from datetime import datetime, timezone

from ..incident import Incident
from ..lifecycle.service import IncidentLifecycleService
from .decision import EscalationDecision
from .level import EscalationLevel
from .policy import DEFAULT_ESCALATION_POLICIES


class IncidentEscalationEngine:

    def __init__(
        self,
        lifecycle: IncidentLifecycleService | None = None,
    ) -> None:

        self.lifecycle = lifecycle or IncidentLifecycleService()

    def evaluate(
        self,
        incident: Incident,
        *,
        now: datetime | None = None,
    ) -> EscalationDecision:

        now = now or datetime.now(timezone.utc)

        policy = DEFAULT_ESCALATION_POLICIES[
            incident.severity
        ]

        current_level = getattr(
            incident,
            "escalation_level",
            policy.initial_level,
        )

        if incident.state.value == "CLOSED":
            return EscalationDecision(
                should_escalate=False,
                current_level=current_level,
                target_level=None,
                reason="incident already closed",
                triggered_at=now,
            )

        elapsed = (
            now - incident.updated_at
        ).total_seconds()

        timeout = self._timeout_for_level(
            policy.timeout_seconds,
            current_level,
        )

        if elapsed < timeout:
            return EscalationDecision(
                should_escalate=False,
                current_level=current_level,
                target_level=None,
                reason="escalation timeout not reached",
                triggered_at=now,
            )

        if current_level >= policy.max_level:
            return EscalationDecision(
                should_escalate=False,
                current_level=current_level,
                target_level=None,
                reason="maximum escalation level reached",
                triggered_at=now,
            )

        target = EscalationLevel(
            current_level + 1
        )

        return EscalationDecision(
            should_escalate=True,
            current_level=current_level,
            target_level=target,
            reason="incident exceeded escalation timeout",
            triggered_at=now,
        )

    def execute(
        self,
        incident: Incident,
        *,
        actor: str = "incident-escalation-engine",
        now: datetime | None = None,
    ) -> EscalationDecision:

        decision = self.evaluate(
            incident,
            now=now,
        )

        if not decision.should_escalate:
            return decision

        incident.escalation_level = (
            decision.target_level
        )

        self.lifecycle.escalate(
            incident,
            actor=actor,
            reason=decision.reason,
        )

        return decision

    @staticmethod
    def _timeout_for_level(
        timeouts: tuple[int, ...],
        level: EscalationLevel,
    ) -> int:

        index = min(
            level.value - 1,
            len(timeouts) - 1,
        )

        return timeouts[index]
