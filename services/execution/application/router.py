from __future__ import annotations

from dataclasses import dataclass

from services.execution.domain.request import (
    ExecutionRequest,
)
from services.execution.domain.routing import (
    ExecutionRoutingPolicy,
)
from services.execution.domain.venue import (
    ExecutionVenue,
)


class NoExecutionVenueAvailable(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class RoutedExecution:
    request: ExecutionRequest
    venue: ExecutionVenue


class ExecutionRouter:

    def __init__(
        self,
        venues: dict[str, ExecutionVenue],
    ) -> None:
        self._venues = dict(venues)

    def route(
        self,
        request: ExecutionRequest,
        policy: ExecutionRoutingPolicy,
    ) -> RoutedExecution:

        policy.validate()

        candidates = self._candidate_venues(
            policy
        )

        for venue_id in candidates:

            venue = self._venues.get(
                venue_id
            )

            if venue is None:
                continue

            if not venue.enabled:
                continue

            return RoutedExecution(
                request=request,
                venue=venue,
            )

        raise NoExecutionVenueAvailable(
            "no enabled execution venue available"
        )

    @staticmethod
    def _candidate_venues(
        policy: ExecutionRoutingPolicy,
    ) -> tuple[str, ...]:

        result: list[str] = []

        if policy.preferred_venue:
            result.append(
                policy.preferred_venue
            )

        for venue in policy.allowed_venues:
            if venue not in result:
                result.append(venue)

        for venue in policy.fallback_venues:
            if venue not in result:
                result.append(venue)

        return tuple(result)
