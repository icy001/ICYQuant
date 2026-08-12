"""
VenueController — per-venue capability gate (failure isolation)
(Commit 26 Part 1.4, spec section 11–12).

If NASDAQ degrades, only NASDAQ is isolated:

    NASDAQ  New Order ❌  Cancel ✅  Reduce ✅
    NYSE    New Order ✅  Cancel ✅  Reduce ✅
    CME     New Order ✅  Cancel ✅  Reduce ✅

The unknown / unhandled state intentionally evaluates as fail-closed
(everything blocked), because an unrecognized venue state must never
silently allow orders through.
"""

from __future__ import annotations

from uuid import UUID

from .audit import (
    VenueControlAuditRecord,
    audit_event_type_for,
)
from .decision import VenueControlDecision
from .policy import VenueControlPolicy
from .state import VenueState


class VenueController:

    def __init__(
        self,
        policy: VenueControlPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or VenueControlPolicy()
        )

        self._states: dict[str, VenueState] = {}

        self._audit_trail: list[VenueControlAuditRecord] = []

    def state(
        self,
        venue: str,
    ) -> VenueState:

        return self._states.get(
            venue,
            VenueState.ONLINE,
        )

    def set_state(
        self,
        venue: str,
        state: VenueState,
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        execution_id: str | None = None,
        actor: str = "venue-controller",
        reason: str = "",
    ) -> None:

        previous_state = self.state(venue)
        self._states[venue] = state

        if previous_state is not state:
            self._audit_trail.append(
                VenueControlAuditRecord(
                    event_type=audit_event_type_for(
                        previous_state,
                        state,
                    ),
                    venue=venue,
                    previous_state=previous_state,
                    new_state=state,
                    incident_id=incident_id,
                    control_id=control_id,
                    execution_id=execution_id,
                    actor=actor,
                    reason=reason,
                )
            )

    def evaluate(
        self,
        venue: str,
    ) -> VenueControlDecision:

        state = self.state(venue)

        if state == VenueState.ONLINE:

            return VenueControlDecision(
                venue=venue,
                state=state,
                allow_new_orders=True,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                reason="venue_online",
            )

        if state == VenueState.DEGRADED:

            return VenueControlDecision(
                venue=venue,
                state=state,
                allow_new_orders=(
                    self.policy.degraded_allow_new
                ),
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                reason="venue_degraded",
            )

        if state == VenueState.PAUSED:

            return VenueControlDecision(
                venue=venue,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                reason="venue_paused",
            )

        if state == VenueState.DISABLED:

            return VenueControlDecision(
                venue=venue,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=(
                    self.policy.disabled_allow_reduce
                ),
                allow_emergency_flatten=True,
                reason="venue_disabled",
            )

        if state == VenueState.FAILOVER:

            return VenueControlDecision(
                venue=venue,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=False,
                allow_emergency_flatten=True,
                reason="venue_failover",
            )

        return VenueControlDecision(
            venue=venue,
            state=state,
            allow_new_orders=False,
            allow_cancel_orders=False,
            allow_reduce_orders=False,
            allow_emergency_flatten=False,
            reason="venue_unknown",
        )

    @property
    def audit_trail(
        self,
    ) -> list[VenueControlAuditRecord]:
        """Immutable view of the state-transition audit trail."""
        return list(self._audit_trail)
