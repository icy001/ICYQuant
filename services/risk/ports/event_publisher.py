"""Risk domain outbound port for publishing risk decision events.

The Risk Domain must not depend on a concrete Event Bus implementation
(Kafka / Redis / RabbitMQ).  Instead it depends on this ``Protocol`` port;
the infrastructure layer provides the actual adapter.
"""

from __future__ import annotations

from typing import Protocol, Union

from ..events import RiskDecisionApproved, RiskDecisionRejected

# Python 3.9 runtime compatibility: ``X | Y`` unions are only valid inside
# annotations, so the alias uses ``typing.Union``.
RiskDecisionEvent = Union[RiskDecisionApproved, RiskDecisionRejected]


class RiskEventPublisher(Protocol):
    """Outbound port: publishes a single risk decision event."""

    def publish(self, event: RiskDecisionEvent) -> None:
        """Publish ``event`` to the underlying event bus.

        Implementations must raise on failure: the service relies on
        exception propagation to preserve failure semantics instead of
        silently losing the event.
        """
        ...
