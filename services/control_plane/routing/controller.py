"""
RoutingController — venue selection with explicit failover
(Commit 26 Part 1.4, spec sections 15–16).

A primary venue (NASDAQ) failing must not silently route to "whatever is
up": routing only ever selects venues whose Venue Control explicitly allows
new orders, and the redirect is recorded in the audit trail.

This layer only establishes the control surface — full smart routing
(instrument support, session, permissions, currency, risk limits, liquidity,
price, venue mapping) is left to the Execution Routing Layer.
"""

from __future__ import annotations

from uuid import UUID

from ..venue.controller import VenueController
from .audit import (
    RoutingAuditEventType,
    RoutingAuditRecord,
)
from .decision import RoutingDecision
from .policy import RoutingPolicy


class RoutingController:

    def __init__(
        self,
        venue_controller: VenueController,
        policy: RoutingPolicy | None = None,
    ) -> None:

        self.venue_controller = venue_controller

        self.policy = (
            policy
            or RoutingPolicy()
        )

        self._audit_trail: list[RoutingAuditRecord] = []

    def select(
        self,
        venues: list[str],
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        execution_id: str | None = None,
        actor: str = "routing-controller",
    ) -> RoutingDecision:

        healthy: list[str] = []

        for venue in venues:

            decision = (
                self.venue_controller
                .evaluate(venue)
            )

            if decision.allow_new_orders:
                healthy.append(venue)

        if not healthy:

            decision = RoutingDecision(
                allowed=False,
                selected_venue=None,
                fallback_venue=None,
                reason="no_available_venue",
            )

            self._audit_trail.append(
                RoutingAuditRecord(
                    event_type=(
                        RoutingAuditEventType.ROUTE_BLOCKED
                    ),
                    venues=tuple(venues),
                    selected_venue=None,
                    fallback_venue=None,
                    reason=decision.reason,
                    incident_id=incident_id,
                    control_id=control_id,
                    execution_id=execution_id,
                    actor=actor,
                )
            )

            return decision

        selected = healthy[0]
        fallback = healthy[1] if len(healthy) > 1 else None

        decision = RoutingDecision(
            allowed=True,
            selected_venue=selected,
            fallback_venue=fallback,
            reason="venue_available",
        )

        event_type = (
            RoutingAuditEventType.ROUTE_REDIRECTED
            if selected != venues[0]
            else RoutingAuditEventType.ROUTE_ALLOWED
        )

        self._audit_trail.append(
            RoutingAuditRecord(
                event_type=event_type,
                venues=tuple(venues),
                selected_venue=selected,
                fallback_venue=fallback,
                reason=decision.reason,
                incident_id=incident_id,
                control_id=control_id,
                execution_id=execution_id,
                actor=actor,
            )
        )

        return decision

    @property
    def audit_trail(
        self,
    ) -> list[RoutingAuditRecord]:
        """Immutable view of the routing-decision audit trail."""
        return list(self._audit_trail)
