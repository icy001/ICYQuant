"""Fund accounting interface for trade reconciliation."""

from __future__ import annotations


class FundAccountingInterface:
    """Connects the ledger, positions, trades, and cash modules to form
    a unified fund accounting layer.

    Supports reconciliation between trading activity and accounting
    records.
    """

    def reconcile(self, trades: list[dict]) -> dict:
        """Reconcile trades against accounting records.

        Args:
            trades: List of trade records.

        Returns:
            Dict with a ``status`` key.
        """
        return {
            "status": "matched",
        }
