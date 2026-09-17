"""Shadow position book — a second ledger, fully isolated (Commit 016 §15/§17).

Shadow positions live next to the broker positions but never touch
them::

    Broker Position 159852 = 0        Shadow Position 159852 = 10,000

is a completely normal state (§17).  A-share ETFs are not shortable in
this track, so a SELL may never exceed the shadow holding — the gate
pre-checks it and the book enforces it again as defense in depth.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional

from .shadow_account import Number, ShadowAccountError


@dataclass
class ShadowPosition:
    """One symbol's shadow holding with average cost and realized PnL."""

    symbol: str
    quantity: int = 0
    avg_cost: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": str(self.avg_cost),
            "realized_pnl": str(self.realized_pnl),
        }


class ShadowPositionBook:
    """Mutable shadow position ledger, updated only by simulated fills."""

    def __init__(self) -> None:
        self._positions: dict[str, ShadowPosition] = {}

    def apply_fill(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: Number,
    ) -> ShadowPosition:
        pos = self._positions.get(symbol)
        if pos is None:
            pos = ShadowPosition(symbol=symbol)
            self._positions[symbol] = pos
        side_u = str(side).upper()
        qty = int(quantity)
        px = Decimal(str(price))
        if side_u == "BUY":
            total_cost = pos.avg_cost * pos.quantity + px * qty
            pos.quantity += qty
            pos.avg_cost = (
                total_cost / pos.quantity if pos.quantity else Decimal("0")
            )
        elif side_u == "SELL":
            if qty > pos.quantity:
                raise ShadowAccountError(
                    "SHADOW_SHORT_SELL_BLOCKED",
                    f"sell {qty} exceeds shadow holding "
                    f"{pos.quantity} of {symbol}",
                )
            pos.realized_pnl += (px - pos.avg_cost) * qty
            pos.quantity -= qty
            if pos.quantity == 0:
                pos.avg_cost = Decimal("0")
        else:
            raise ValueError(f"unsupported shadow side: {side!r}")
        return pos

    def get(self, symbol: str) -> Optional[ShadowPosition]:
        return self._positions.get(symbol)

    def quantity(self, symbol: str) -> int:
        pos = self._positions.get(symbol)
        return pos.quantity if pos else 0

    def positions(self) -> list[ShadowPosition]:
        """Open positions only (quantity != 0)."""
        return [p for p in self._positions.values() if p.quantity != 0]

    def all_positions(self) -> list[ShadowPosition]:
        return list(self._positions.values())

    def realized_pnl(self) -> Decimal:
        return sum(
            (p.realized_pnl for p in self._positions.values()),
            Decimal("0"),
        )

    def market_value(self, prices: Mapping[str, Number]) -> Decimal:
        total = Decimal("0")
        for pos in self.positions():
            price = prices.get(pos.symbol)
            if price is not None:
                total += Decimal(str(price)) * pos.quantity
        return total

    def as_list(self) -> list[dict]:
        return [p.as_dict() for p in self.positions()]


__all__ = ["ShadowPosition", "ShadowPositionBook"]
