"""Account balance — the money half of an account snapshot (§2).

Currency is a field, not a hard-coded ``CNY`` (§2): the A-share phase
only ever produces CNY, but a Singapore / US account reuses the model
unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from .values import money, to_decimal

#: Tolerance for the balance identity — a cent of rounding noise.
_BALANCE_TOLERANCE = Decimal("0.01")


_ZERO = Decimal("0")


@dataclass(frozen=True)
class AccountBalance:
    """A point-in-time account balance (§2).

    ``broker_timestamp`` is the broker's own snapshot time and
    ``received_timestamp`` when ICYQuant pulled it, so ``sync_latency``
    can be derived and a *stale broker payload* is detectable (§13).
    """

    account_id: str
    currency: str = "CNY"

    cash: Decimal = _ZERO
    available_cash: Decimal = _ZERO
    frozen_cash: Decimal = _ZERO

    market_value: Decimal = _ZERO
    total_asset: Decimal = _ZERO

    buying_power: Decimal = _ZERO

    broker_timestamp: Optional[datetime] = None
    received_timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id must not be empty")
        for name in (
            "cash",
            "available_cash",
            "frozen_cash",
            "market_value",
            "total_asset",
            "buying_power",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                object.__setattr__(self, name, money(value))

    # ── consistency (§3 — a failure is INVALID, never silently fixed) ──

    @property
    def usable_cash_consistent(self) -> bool:
        """``cash == available_cash + frozen_cash``."""
        return abs(
            self.cash - (self.available_cash + self.frozen_cash)
        ) <= _BALANCE_TOLERANCE

    @property
    def total_consistent(self) -> bool:
        """``total_asset == cash + market_value``."""
        return abs(
            self.total_asset - (self.cash + self.market_value)
        ) <= _BALANCE_TOLERANCE

    @property
    def consistent(self) -> bool:
        return self.usable_cash_consistent and self.total_consistent

    def inconsistencies(self) -> list[str]:
        """Human-readable list of broken identities (empty == consistent)."""
        problems: list[str] = []
        if not self.usable_cash_consistent:
            problems.append(
                "cash != available_cash + frozen_cash "
                f"({self.cash} != {self.available_cash} + {self.frozen_cash})"
            )
        if not self.total_consistent:
            problems.append(
                "total_asset != cash + market_value "
                f"({self.total_asset} != {self.cash} + {self.market_value})"
            )
        return problems

    @property
    def position_value(self) -> Decimal:
        """Alias kept explicit so callers don't confuse it with ``cash``."""
        return self.market_value

    def derive_missing(self) -> "AccountBalance":
        """Fill only *unambiguously derivable* fields.

        A broker that omits ``cash`` but gives available + frozen is
        fine; a broker that omits ``total_asset`` but gives cash +
        market value is fine.  Anything genuinely absent stays ``0`` and
        is reported by :meth:`inconsistencies` instead of being invented.
        """
        cash = self.cash
        if cash == _ZERO and (
            self.available_cash != _ZERO or self.frozen_cash != _ZERO
        ):
            cash = self.available_cash + self.frozen_cash
        total = self.total_asset
        if total == _ZERO and (cash != _ZERO or self.market_value != _ZERO):
            total = cash + self.market_value
        buying_power = self.buying_power
        if buying_power == _ZERO and self.available_cash != _ZERO:
            buying_power = self.available_cash
        return AccountBalance(
            account_id=self.account_id,
            currency=self.currency,
            cash=cash,
            available_cash=self.available_cash,
            frozen_cash=self.frozen_cash,
            market_value=self.market_value,
            total_asset=total,
            buying_power=buying_power,
            broker_timestamp=self.broker_timestamp,
            received_timestamp=self.received_timestamp,
        )

    def with_market_value(
        self, market_value: Any = None, total_asset: Any = None
    ) -> "AccountBalance":
        """Return a copy with the §18 valuation applied.

        Accepts the same ``Decimal`` / ``str`` / ``int`` inputs as the
        constructor: the market value is coerced *once* so the totals
        identity below can never add a ``str`` to a ``Decimal``.
        """
        value = money(market_value)
        return AccountBalance(
            account_id=self.account_id,
            currency=self.currency,
            cash=self.cash,
            available_cash=self.available_cash,
            frozen_cash=self.frozen_cash,
            market_value=value,
            total_asset=(
                money(total_asset)
                if total_asset is not None
                else money(self.cash + value)
            ),
            buying_power=self.buying_power,
            broker_timestamp=self.broker_timestamp,
            received_timestamp=self.received_timestamp,
        )

    def as_dict(self) -> dict:
        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "account_id": self.account_id,
            "currency": self.currency,
            "cash": _f(self.cash),
            "available_cash": _f(self.available_cash),
            "frozen_cash": _f(self.frozen_cash),
            "market_value": _f(self.market_value),
            "total_asset": _f(self.total_asset),
            "buying_power": _f(self.buying_power),
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
            "consistent": self.consistent,
        }


__all__ = ["AccountBalance"]
