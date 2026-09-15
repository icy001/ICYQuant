"""Commit 015 §4 / §9 — Position Ledger read integration.

§4 draws the line this module exists to respect::

    Broker Position    the broker's reported truth  (§3)
    Position Ledger    ICYQuant's own bookkeeping    ← this module reads it
    Strategy Position  what the strategy *thinks*     (never conflated here)

The sync pipeline reads the ledger to reconcile it against the broker;
it **never writes** to it (§23 — no automatic correction / no silent
ledger edit).  Rather than create a second position book (§23), the
:class:`ProjectionPositionLedgerReader` adapts the project's existing
Position Ledger projection by duck-typing its ``state`` mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from services.account.domain.values import money_or_none, quantity as to_qty

_ZERO = Decimal("0")


@dataclass(frozen=True)
class LedgerPosition:
    """One position as ICYQuant's ledger believes it (§9)."""

    account_id: str
    symbol: str
    quantity: Decimal = _ZERO
    available_quantity: Optional[Decimal] = None
    average_cost: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    exchange: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.quantity, Decimal):
            object.__setattr__(self, "quantity", to_qty(self.quantity))
        for name in ("available_quantity", "average_cost", "market_value"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                object.__setattr__(self, name, money_or_none(value))

    def as_dict(self) -> dict:
        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "account_id": self.account_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "quantity": _f(self.quantity),
            "available_quantity": _f(self.available_quantity),
            "average_cost": _f(self.average_cost),
            "market_value": _f(self.market_value),
        }


@dataclass(frozen=True)
class LedgerBalance:
    """Ledger-side cash view, when the ledger tracks a balance (§10)."""

    account_id: str
    cash: Optional[Decimal] = None
    available_cash: Optional[Decimal] = None
    frozen_cash: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    total_asset: Optional[Decimal] = None

    def __post_init__(self) -> None:
        for name in (
            "cash",
            "available_cash",
            "frozen_cash",
            "market_value",
            "total_asset",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                object.__setattr__(self, name, money_or_none(value))

    def as_dict(self) -> dict:
        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "account_id": self.account_id,
            "cash": _f(self.cash),
            "available_cash": _f(self.available_cash),
            "frozen_cash": _f(self.frozen_cash),
            "market_value": _f(self.market_value),
            "total_asset": _f(self.total_asset),
        }


@runtime_checkable
class PositionLedgerReader(Protocol):
    """The read-only ledger port reconciliation needs (§9)."""

    def positions(self, account_id: str) -> list[LedgerPosition]:
        """Ledger positions for ``account_id``."""

    def balance(self, account_id: str) -> Optional[LedgerBalance]:
        """Ledger balance for ``account_id`` (``None`` if untracked)."""


class InMemoryPositionLedgerReader:
    """Dict-backed :class:`PositionLedgerReader` (tests / default wiring)."""

    def __init__(
        self,
        positions: Optional[Mapping[str, list[LedgerPosition]]] = None,
        balances: Optional[Mapping[str, LedgerBalance]] = None,
    ) -> None:
        self._positions: dict[str, list[LedgerPosition]] = {
            k: list(v) for k, v in (positions or {}).items()
        }
        self._balances: dict[str, LedgerBalance] = dict(balances or {})

    def set_positions(
        self, account_id: str, rows: list[LedgerPosition]
    ) -> None:
        self._positions[account_id] = list(rows)

    def set_balance(self, account_id: str, balance: LedgerBalance) -> None:
        self._balances[account_id] = balance

    def positions(self, account_id: str) -> list[LedgerPosition]:
        return list(self._positions.get(account_id, []))

    def balance(self, account_id: str) -> Optional[LedgerBalance]:
        return self._balances.get(account_id)

    def clear(self) -> None:
        self._positions.clear()
        self._balances.clear()


class ProjectionPositionLedgerReader:
    """Adapts the project's existing Position Ledger projection (§23).

    The ledger's ``PositionProjection`` already maintains
    ``state = {symbol: {quantity, avg_cost, ...}}``; this reader projects
    that state into :class:`LedgerPosition` so a **second ledger is not
    created**.  The projection object is duck-typed (``.state``), so the
    heavy ledger package is never imported here.
    """

    _QUANTITY_KEYS = ("quantity", "qty", "volume", "position", "current_amount")
    _COST_KEYS = ("avg_cost", "average_cost", "cost", "cost_price")
    _AVAILABLE_KEYS = ("available_quantity", "available", "avail_qty")
    _VALUE_KEYS = ("market_value", "value")

    def __init__(
        self,
        projection: Any,
        *,
        account_id: str = "",
        balance: Optional[LedgerBalance] = None,
        quantity_keys: Optional[tuple[str, ...]] = None,
        cost_keys: Optional[tuple[str, ...]] = None,
    ) -> None:
        self._projection = projection
        self._account_id = account_id
        self._balance = balance
        self._quantity_keys = quantity_keys or self._QUANTITY_KEYS
        self._cost_keys = cost_keys or self._COST_KEYS

    @staticmethod
    def _pick(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        return None

    def _state(self) -> Mapping[str, Any]:
        state = getattr(self._projection, "state", None)
        if state is None and isinstance(self._projection, Mapping):
            state = self._projection
        if state is None and callable(getattr(self._projection, "as_dict", None)):
            state = self._projection.as_dict()
        return state or {}

    def positions(self, account_id: str) -> list[LedgerPosition]:
        resolved_account = account_id or self._account_id
        rows: list[LedgerPosition] = []
        for symbol, row in sorted(self._state().items()):
            payload = row if isinstance(row, Mapping) else {"quantity": row}
            rows.append(
                LedgerPosition(
                    account_id=resolved_account,
                    symbol=str(symbol),
                    quantity=self._pick(payload, self._quantity_keys) or _ZERO,
                    available_quantity=self._pick(payload, self._AVAILABLE_KEYS),
                    average_cost=self._pick(payload, self._cost_keys),
                    market_value=self._pick(payload, self._VALUE_KEYS),
                )
            )
        return rows

    def balance(self, account_id: str) -> Optional[LedgerBalance]:
        return self._balance


__all__ = [
    "LedgerPosition",
    "LedgerBalance",
    "PositionLedgerReader",
    "InMemoryPositionLedgerReader",
    "ProjectionPositionLedgerReader",
]
