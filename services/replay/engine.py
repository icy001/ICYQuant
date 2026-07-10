"""
Replay engine.

Responsible for rebuilding
application state from ledger events.

The replay engine never changes
ledger data.

It only rebuilds projections.
"""

from __future__ import annotations


from collections.abc import Iterable


from services.ledger import LedgerEvent


from services.projection import (
    ProjectionEngine,
    PortfolioState,
)


class ReplayEngine:
    """
    Rebuild portfolio state
    from immutable ledger events.
    """

    def __init__(
        self,
        projection_engine: ProjectionEngine,
        state: PortfolioState,
    ) -> None:
        self.projection_engine = (
            projection_engine
        )

        self.state = state

    def replay(
        self,
        events: Iterable[LedgerEvent],
    ) -> PortfolioState:
        """
        Replay events sequentially.
        """
        for event in events:
            self.projection_engine.apply(
                event
            )

        return self.state

    def rebuild(
        self,
        events: Iterable[LedgerEvent],
    ) -> PortfolioState:
        """
        Alias for full rebuild.

        Used by:

        - recovery
        - reconciliation
        - testing
        """
        return self.replay(
            events
        )