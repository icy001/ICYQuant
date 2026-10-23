"""Mock market data adapter.

Generates synthetic but realistic A-share ETF/LOF quotes for
development and paper trading.  This is the ONLY adapter in
Commit 001 — real broker adapters come later and must implement
the same interface, so downstream code never changes.

Price model: random walk around a per-symbol base price with
small per-tick jitter.  Bid/ask are derived from last with a
realistic spread (1 tick = 0.001 for A-share ETFs).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterator, Optional

from ..domain.instrument import Exchange, Instrument
from ..domain.quote import MarketQuote
from ..exceptions.market_data_error import (
    AdapterAlreadyConnectedError,
    AdapterNotConnectedError,
)
from .base import MarketDataAdapter

logger = logging.getLogger(__name__)

# 11 seed symbols with base prices (approximate real values)
_SEED_PRICES: dict[str, Decimal] = {
    "159852": Decimal("1.050"),   # 创业板ETF
    "513050": Decimal("1.620"),   # 中证500ETF
    "159890": Decimal("0.950"),   # 科创50ETF
    "159559": Decimal("0.820"),   # 科创100ETF
    "159569": Decimal("1.280"),   # 创业板50ETF
    "515880": Decimal("0.690"),   # 红利ETF
    "159871": Decimal("1.150"),   # 中证1000ETF (QDII-ETF)
    "513310": Decimal("2.350"),   # 日经225ETF (QDII-ETF)
    "501225": Decimal("1.480"),   # 日经225ETF (QDII-LOF)
    "161116": Decimal("1.050"),   # 创业板ETF (LOF)
    "165520": Decimal("1.320"),   # 日经225ETF (QDII-LOF)
}

_TICK_SIZE = Decimal("0.001")


class MockMarketDataAdapter(MarketDataAdapter):
    """Synthetic quote generator for A-share funds.

    Usage::

        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        for quote in adapter.stream():
            print(quote)

    The stream is infinite — the caller controls how many quotes
    to consume (``itertools.islice`` or break on condition).
    """

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        max_quotes: Optional[int] = None,
    ) -> None:
        self._connected = False
        self._subscribed: set[str] = set()
        self._prices: dict[str, Decimal] = dict(_SEED_PRICES)
        self._volumes: dict[str, int] = {s: 0 for s in self._prices}
        self._turnovers: dict[str, Decimal] = {s: Decimal("0") for s in self._prices}
        # symbol → (open, high, low, pre_close)
        self._ohlc: dict[str, tuple] = {}
        self._rng = random.Random(seed)
        self._max_quotes = max_quotes  # None = infinite
        self._quote_count = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._require_disconnected()
        self._connected = True
        logger.info("MockMarketDataAdapter connected")

    def disconnect(self) -> None:
        if not self._connected:
            return
        self._connected = False
        self._subscribed.clear()
        logger.info("MockMarketDataAdapter disconnected")

    def subscribe(self, symbols: list[str]) -> None:
        self._require_connected()
        for sym in symbols:
            if sym not in self._prices:
                logger.warning(
                    "mock adapter: unknown symbol %s, "
                    "registering with default price 1.000",
                    sym,
                )
                self._prices[sym] = Decimal("1.000")
                self._volumes[sym] = 0
            self._subscribed.add(sym)
            logger.debug("mock adapter: subscribed %s", sym)

    def unsubscribe(self, symbols: list[str]) -> None:
        self._require_connected()
        for sym in symbols:
            self._subscribed.discard(sym)
            logger.debug("mock adapter: unsubscribed %s", sym)

    @property
    def subscribed_symbols(self) -> set[str]:
        """Read-only view of currently subscribed symbols."""
        return set(self._subscribed)

    def stream(self) -> Iterator[MarketQuote]:
        self._require_connected()
        if not self._subscribed:
            return
        while True:
            if self._max_quotes is not None and self._quote_count >= self._max_quotes:
                return
            yield self._next_quote()
            self._quote_count += 1

    # ── internals ───────────────────────────────────────────────

    def _next_quote(self) -> MarketQuote:
        """Generate one quote for a random subscribed symbol."""
        sym = self._rng.choice(list(self._subscribed))
        base = self._prices[sym]

        # Random walk: ±0.3% per tick, rounded to tick size
        pct = Decimal(str(self._rng.uniform(-0.003, 0.003)))
        new_price = (base * (1 + pct)).quantize(_TICK_SIZE, rounding=ROUND_HALF_UP)
        # Clamp to >= 0.001
        if new_price < _TICK_SIZE:
            new_price = _TICK_SIZE
        self._prices[sym] = new_price

        # Bid/ask derived from last with 1-tick spread
        bid = new_price - _TICK_SIZE
        ask = new_price
        if bid < _TICK_SIZE:
            bid = new_price
            ask = new_price + _TICK_SIZE

        # Sizes: 10-200 lots (1000-20000 shares)
        bid_size = self._rng.randint(10, 200) * 100
        ask_size = self._rng.randint(10, 200) * 100

        # Volume: accumulate; turnover = volume * price (approximate)
        traded = self._rng.randint(100, 500) * 100
        self._volumes[sym] += traded
        turnover_add = (Decimal(traded) * new_price).quantize(Decimal("0.01"))
        self._turnovers[sym] = self._turnovers.get(sym, Decimal("0")) + turnover_add

        # OHLC session tracking (per adapter instance = session)
        open_p, high_p, low_p, pre_close = self._ohlc.get(
            sym, (new_price, new_price, new_price, base)
        )
        high_p = max(high_p, new_price)
        low_p = min(low_p, new_price)
        self._ohlc[sym] = (open_p, high_p, low_p, pre_close)

        exchange = Instrument.infer_exchange(sym)

        return MarketQuote(
            symbol=sym,
            exchange=exchange,
            timestamp=datetime.now(timezone.utc),
            last=new_price,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            volume=self._volumes[sym],
            turnover=self._turnovers[sym],
            open=open_p,
            high=high_p,
            low=low_p,
            pre_close=pre_close,
        )


__all__ = ["MockMarketDataAdapter"]
