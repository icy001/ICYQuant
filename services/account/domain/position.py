"""Broker position — the quantity half of an account snapshot (§3).

Two invariants the whole commit rests on:

1. ``quantity == available_quantity + frozen_quantity`` (§3).  A broker
   payload that breaks this is ``INVALID`` and goes to the exception /
   reconciliation path — it is **never** silently patched.
2. ``available_quantity`` is taken **as the broker reported it** (§19).
   A T+1 buy shows ``quantity=10000, available=0``; deriving
   ``available = quantity`` is exactly the bug §19 forbids.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .enums import PositionStatus
from .exceptions import InvalidPositionError
from .values import money, money_or_none, quantity as qty

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Position:
    """A broker-reported holding (§3) plus its §18 valuation."""

    account_id: str
    symbol: str
    exchange: str

    quantity: Decimal = _ZERO
    available_quantity: Decimal = _ZERO
    frozen_quantity: Decimal = _ZERO

    average_cost: Decimal = _ZERO

    #: Filled by the §18 valuation step (Market Data price), never by the
    #: account adapter, and ``None`` until a price exists.
    market_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[Decimal] = None

    broker_timestamp: Optional[datetime] = None
    received_timestamp: Optional[datetime] = None

    status: str = PositionStatus.VALID.value

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id must not be empty")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        for name in ("quantity", "available_quantity", "frozen_quantity"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                object.__setattr__(self, name, qty(value))
        if not isinstance(self.average_cost, Decimal):
            object.__setattr__(self, "average_cost", money(self.average_cost))
        for name in (
            "market_price",
            "market_value",
            "unrealized_pnl",
            "unrealized_pnl_pct",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                object.__setattr__(self, name, money_or_none(value))

    # ── consistency (§3) ──────────────────────────────────────────────

    @property
    def consistent(self) -> bool:
        """``quantity == available_quantity + frozen_quantity``."""
        return self.quantity == (self.available_quantity + self.frozen_quantity)

    @property
    def is_valid(self) -> bool:
        return self.status == PositionStatus.VALID.value and self.consistent

    def inconsistencies(self) -> list[str]:
        problems: list[str] = []
        if not self.consistent:
            problems.append(
                "quantity != available_quantity + frozen_quantity "
                f"({self.quantity} != {self.available_quantity} "
                f"+ {self.frozen_quantity})"
            )
        if self.quantity < _ZERO:
            problems.append(f"negative quantity ({self.quantity})")
        if self.available_quantity < _ZERO:
            problems.append(f"negative available_quantity ({self.available_quantity})")
        if self.average_cost < _ZERO:
            problems.append(f"negative average_cost ({self.average_cost})")
        return problems

    def validate(self) -> "Position":
        """Raise :class:`InvalidPositionError` if inconsistent (§3).

        Returns ``self`` so callers can chain.  Never mutates the numbers
        to make them agree.
        """
        problems = self.inconsistencies()
        if problems:
            raise InvalidPositionError(
                f"invalid position {self.symbol}: " + "; ".join(problems),
                account_id=self.account_id,
                symbol=self.symbol,
            )
        return self

    def as_invalid(self) -> "Position":
        """A copy explicitly marked ``INVALID`` (used by reconciliation)."""
        return self._replace(status=PositionStatus.INVALID.value)

    # ── helpers ───────────────────────────────────────────────────────

    def _replace(self, **changes: object) -> "Position":
        from dataclasses import replace as _dc_replace

        return _dc_replace(self, **changes)

    #: Alias so callers don't need to import ``dataclasses`` — matches the
    #: frozen-dataclass idiom used across the market-data domain.
    replace = _replace

    def with_valuation(
        self,
        price: Optional[Decimal],
        timestamp: Optional[datetime] = None,
    ) -> "Position":
        """Return a copy carrying the §18 Market-Data valuation.

        ``market_value = quantity * price`` and
        ``unrealized_pnl = (price - average_cost) * quantity``.  With no
        price the valuation fields stay ``None`` — never a fabricated 0.
        """
        if price is None:
            return self
        price = money(price)
        market_value = money(self.quantity * price)
        cost_basis = money(self.average_cost * self.quantity)
        pnl = money(market_value - cost_basis)
        pnl_pct = None
        if cost_basis != _ZERO:
            pnl_pct = money(pnl / cost_basis * Decimal("100"))
        return self._replace(
            market_price=price,
            market_value=market_value,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            received_timestamp=timestamp or self.received_timestamp,
        )

    def as_dict(self) -> dict:
        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "account_id": self.account_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "quantity": _f(self.quantity),
            "available_quantity": _f(self.available_quantity),
            "frozen_quantity": _f(self.frozen_quantity),
            "average_cost": _f(self.average_cost),
            "market_price": _f(self.market_price),
            "market_value": _f(self.market_value),
            "unrealized_pnl": _f(self.unrealized_pnl),
            "unrealized_pnl_pct": _f(self.unrealized_pnl_pct),
            "status": self.status,
            "consistent": self.consistent,
            "broker_timestamp": (
                self.broker_timestamp.isoformat()
                if self.broker_timestamp
                else None
            ),
            "received_timestamp": (
                self.received_timestamp.isoformat()
                if self.received_timestamp
                else None
            ),
        }


__all__ = ["Position"]
