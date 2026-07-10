"""
Projection engine.

Consumes ledger events
and updates projections.
"""

from __future__ import annotations


from services.ledger import LedgerEvent


from .base import Projection


class ProjectionEngine:
    def __init__(
        self,
        projections: list[Projection],
    ) -> None:
        self.projections = projections

    def apply(
        self,
        event: LedgerEvent,
    ) -> None:
        for projection in self.projections:
            projection.apply(
                event
            )

    def apply_many(
        self,
        events: list[LedgerEvent],
    ) -> None:
        for event in events:
            self.apply(event)

    def replay(
        self,
        events: list[LedgerEvent],
    ) -> None:
        for event in events:
            self.apply(
                event
            )