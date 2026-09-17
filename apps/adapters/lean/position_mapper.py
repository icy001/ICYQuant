"""LEAN positions → ICYQuant positions.

LEAN expresses a position as a single signed quantity; ICYQuant's
downstream consumers (ledger, reconciliation, risk) want an explicit
side.  ``FLAT`` is spelled out rather than left as a zero quantity so a
closed position can never be mistaken for a missing one.
"""
from __future__ import annotations

from typing import Any

__all__ = ["map_lean_position", "position_side"]


def position_side(quantity: float) -> str:
    """LONG / SHORT / FLAT for a signed quantity."""
    if quantity > 0:
        return "LONG"

    if quantity < 0:
        return "SHORT"

    return "FLAT"


def map_lean_position(position: dict[str, Any]) -> dict[str, Any]:
    """Normalise a LEAN position record."""
    quantity = float(position.get("quantity", 0) or 0)

    return {
        "symbol": position.get("symbol"),
        "quantity": quantity,
        "side": position_side(quantity),
        "avg_price": position.get("avg_price"),
        "market_price": position.get("market_price"),
        "market_value": position.get("market_value"),
        "unrealized_pnl": position.get("unrealized_pnl"),
    }
