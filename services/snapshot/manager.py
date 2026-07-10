"""
Snapshot manager.

Creates and restores snapshots.
"""

from __future__ import annotations


from uuid import uuid4


from datetime import datetime, timezone


from services.projection import (
    PortfolioState,
)


from .model import (
    PortfolioSnapshot,
)


class SnapshotManager:
    def create(
        self,
        state: PortfolioState,
        event_id,
    ) -> PortfolioSnapshot:
        """
        Create state snapshot.
        """
        return PortfolioSnapshot(
            snapshot_id=uuid4(),
            event_id=event_id,
            created_at=datetime.now(
                timezone.utc
            ),
            state=self.serialize(
                state
            )
        )

    def serialize(
        self,
        state: PortfolioState,
    ) -> dict:
        return {
            "positions": {
                symbol: {
                    "quantity":
                        str(position.quantity),
                    "average_price":
                        str(position.average_price),
                }
                for symbol, position
                in state.positions.items()
            },
            "cash": {
                currency: {
                    "balance":
                        str(value.balance)
                }
                for currency, value
                in state.cash.items()
            }
        }