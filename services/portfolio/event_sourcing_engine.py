"""
Portfolio event sourcing engine.
"""

from datetime import datetime

from .event import PortfolioEvent


class PortfolioEventSourcingEngine:

    def __init__(
        self,
        repository,
        publisher,
    ):

        self.repository = repository

        self.publisher = publisher

    def record(
        self,
        event_id,
        event_type,
        portfolio_id,
        payload,
    ):

        event = PortfolioEvent(
            event_id=event_id,
            event_type=event_type,
            portfolio_id=portfolio_id,
            occurred_at=datetime.utcnow(),
            payload=payload,
        )

        self.repository.save(
            event
        )

        self.publisher.publish(
            event
        )

        return event