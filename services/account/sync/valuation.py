"""Commit 015 §18 — the single place quantity meets Market Data price.

The rule §18 fixes::

    Position Quantity   ← Broker Account          (authoritative)
    market_price        ← ICYQuant Market Data    (authoritative)
    market_value / PnL  ← this module (quantity × price)

so ICYQuant never runs "a broker price system" beside "a market-data
price system".  The account adapter never fetches a quote (§18) and the
normalizer never sets a price; valuation happens here, once, with a
price provider injected by the caller.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Mapping, Optional, Protocol

from services.account.domain.balance import AccountBalance
from services.account.domain.position import Position
from services.account.domain.values import money, to_decimal

logger = logging.getLogger(__name__)


class PriceProvider(Protocol):
    """Minimal Market Data price port (§18)."""

    def last_price(self, symbol: str) -> Optional[Decimal]:
        """Latest price for ``symbol``, or ``None`` if unavailable."""


class MappingPriceProvider:
    """A dict-backed :class:`PriceProvider` (tests / offline wiring).

    Accepts any value :func:`~services.account.domain.values.to_decimal`
    understands, so ``{"159852": "1.28"}`` works.
    """

    def __init__(self, prices: Optional[Mapping[str, Any]] = None) -> None:
        self._prices: dict[str, Decimal] = {}
        self.update(prices or {})

    def update(self, prices: Mapping[str, Any]) -> None:
        for symbol, value in prices.items():
            self.set_price(symbol, value)

    def set_price(self, symbol: str, value: Any) -> None:
        parsed = to_decimal(value)
        if parsed is None:
            self._prices.pop(str(symbol), None)
        else:
            self._prices[str(symbol)] = parsed

    def last_price(self, symbol: str) -> Optional[Decimal]:
        return self._prices.get(str(symbol))

    @property
    def symbols(self) -> list[str]:
        return sorted(self._prices)

    def as_dict(self) -> dict:
        return {k: float(v) for k, v in sorted(self._prices.items())}


#: Backwards-friendly alias.
StaticPriceProvider = MappingPriceProvider


#: Quality-Gate verdicts whose price is still trusted for valuation (§18).
_TRUSTED_QUALITY: frozenset[str] = frozenset({"FRESH", "WARNING"})


class MarketDataPriceProvider:
    """A :class:`PriceProvider` backed by the unified Market Data service.

    This is the §18 meeting point in production: quantity comes from the
    broker, the price comes from ICYQuant's own Market Data pipeline —
    never from the broker's account API.

    Two deliberate properties:

    * **Only trusted prices are used.**  A quote whose Quality Gate verdict
      is ``STALE`` / ``INVALID`` / ``QUARANTINED`` is treated as *no price*
      so ``market_value`` stays ``None`` (§18 — never a fabricated number
      computed from suspect data).
    * **Never raises.**  Market Data being unavailable must not fail an
      account sync: the snapshot is still recorded, simply unvalued.  The
      failure is logged once rather than per position.

    The Market Data import is deferred to first use, so importing the
    account package never drags in the quote pipeline.
    """

    def __init__(
        self,
        quotes_fn: Optional[Any] = None,
        *,
        trusted: frozenset[str] = _TRUSTED_QUALITY,
    ) -> None:
        self._quotes_fn = quotes_fn
        self._trusted = frozenset(s.upper() for s in trusted)
        self._warned = False

    def _resolve_quotes_fn(self):
        if self._quotes_fn is None:
            from services.market_data.market_data_service import (
                market_data_service,
            )

            self._quotes_fn = market_data_service.quotes
        return self._quotes_fn

    def last_price(self, symbol: str) -> Optional[Decimal]:
        symbol = str(symbol)
        try:
            payload = self._resolve_quotes_fn()([symbol])
        except Exception as exc:  # noqa: BLE001 - valuation is best-effort
            if not self._warned:
                self._warned = True
                logger.warning(
                    "market data unavailable for valuation (%s); "
                    "snapshots will be stored unvalued",
                    exc,
                )
            return None
        items = payload.get("items") or []
        if not items:
            return None
        item = items[0]
        if item.get("last") is None:
            return None
        quality = item.get("quality") or {}
        verdict = str(quality.get("status") or "FRESH").upper()
        if verdict not in self._trusted:
            return None
        return to_decimal(item["last"])

    def as_dict(self) -> dict:
        return {
            "source": "market_data_service",
            "trusted_quality": sorted(self._trusted),
        }


class PositionValuator:
    """Applies Market Data prices to broker positions + balance (§18)."""

    def __init__(
        self,
        price_provider: Optional[PriceProvider] = None,
        *,
        enabled: bool = True,
    ) -> None:
        self._prices = price_provider
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled and self._prices is not None

    def value_position(self, position: Position) -> Position:
        """Return ``position`` with §18 valuation applied (or unchanged)."""
        if not self.enabled:
            return position
        price = self._prices.last_price(position.symbol)
        if price is None:
            return position
        return position.with_valuation(price)

    def value_positions(self, positions: list[Position]) -> list[Position]:
        return [self.value_position(p) for p in positions]

    def value_balance(
        self,
        balance: Optional[AccountBalance],
        positions: list[Position],
    ) -> Optional[AccountBalance]:
        """Recompute the balance's ``market_value`` / ``total_asset`` (§18).

        Only when **every** position has a price: a partial sum would be a
        fabricated number, so the broker's own ``market_value`` is kept
        instead when prices are incomplete.
        """
        if balance is None:
            return None
        if not self.enabled or not positions:
            return balance
        if any(p.market_value is None for p in positions):
            return balance
        market_value = money(
            sum((p.market_value for p in positions if p.market_value), Decimal("0"))
        )
        return balance.with_market_value(market_value)


__all__ = [
    "PriceProvider",
    "MappingPriceProvider",
    "StaticPriceProvider",
    "MarketDataPriceProvider",
    "PositionValuator",
]
