"""Shadow account — imaginary cash, real discipline (Commit 016 §16).

The Shadow account is configured capital, deliberately **not** the real
broker balance: Shadow is a separate ledger that must stay isolated
from the broker account (§15).  The only thing it shares with Paper's
account is the discipline — a BUY that the cash cannot cover never
executes.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Union


class ShadowAccountError(RuntimeError):
    """Machine-readable Shadow account failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


Number = Union[Decimal, int, str, float]


class ShadowAccount:
    """Cash leg of the Shadow ledger.

    ``initial_capital`` is user configuration (§16) — the default of
    1,000,000 CNY is a starting point, never a binding to any real
    account.
    """

    def __init__(self, initial_capital: Number = Decimal("1000000")) -> None:
        self.initial_capital = Decimal(str(initial_capital))
        self.cash = Decimal(str(initial_capital))

    def apply_fill(
        self,
        side: str,
        quantity: int,
        price: Number,
        commission: Number = 0,
    ) -> None:
        """Apply one simulated fill to the cash leg.

        Raises :class:`ShadowAccountError` with ``SHADOW_INSUFFICIENT_CASH``
        rather than going negative — the gate pre-checks this, so a raise
        here means a bug, not a trading decision.
        """
        side_u = str(side).upper()
        notional = Decimal(str(price)) * int(quantity)
        fee = Decimal(str(commission))
        if side_u == "BUY":
            cost = notional + fee
            if cost > self.cash:
                raise ShadowAccountError(
                    "SHADOW_INSUFFICIENT_CASH",
                    f"buy cost {cost} exceeds shadow cash {self.cash}",
                )
            self.cash -= cost
        elif side_u == "SELL":
            self.cash += notional - fee
        else:
            raise ValueError(f"unsupported shadow side: {side!r}")

    def as_dict(self) -> dict:
        return {
            "initial_capital": str(self.initial_capital),
            "cash": str(self.cash),
        }


__all__ = ["ShadowAccount", "ShadowAccountError"]
