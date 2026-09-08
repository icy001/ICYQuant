"""A-share ETF / LOF Universe — the single source of truth for
trading instruments in ICYQuant.

Commit 002 formally registers the 11 seed symbols with authoritative
metadata (name, exchange, type, currency, lot_size, tick_size,
enabled).  All downstream modules (Strategy, Paper Trading, Dashboard,
Market Data Adapter, Broker Adapter) must reference this registry
instead of maintaining their own symbol lists.

Adding or removing a trading instrument only changes this file —
nothing else in ICYQuant needs to be modified.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .domain.instrument import (
    Exchange,
    Instrument,
    InstrumentType,
    TradingStatus,
)


# ── The 11 seed symbols ───────────────────────────────────────
# Authoritative metadata for each instrument.  Exchange and type
# are set explicitly (not inferred) because some codes have
# non-obvious classifications (e.g. 161116 is QDII-LOF, not plain
# LOF; 165520 is LOF, not QDII).

_SEED_DATA: list[dict] = [
    {
        "symbol": "159852",
        "name": "软件ETF",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "513050",
        "name": "中概互联网ETF",
        "exchange": Exchange.SSE,
        "instrument_type": InstrumentType.QDII_ETF,
    },
    {
        "symbol": "159890",
        "name": "云计算ETF",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "159559",
        "name": "机器人ETF",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "159569",
        "name": "港股红利低波ETF",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "515880",
        "name": "通信ETF",
        "exchange": Exchange.SSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "159871",
        "name": "有色ETF",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.ETF,
    },
    {
        "symbol": "513310",
        "name": "中韩半导体ETF",
        "exchange": Exchange.SSE,
        "instrument_type": InstrumentType.QDII_ETF,
    },
    {
        "symbol": "501225",
        "name": "全球半导体芯片",
        "exchange": Exchange.SSE,
        "instrument_type": InstrumentType.QDII_LOF,
    },
    {
        "symbol": "161116",
        "name": "易方达黄金主题",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.QDII_LOF,
    },
    {
        "symbol": "165520",
        "name": "中信保诚有色指数",
        "exchange": Exchange.SZSE,
        "instrument_type": InstrumentType.LOF,
    },
]


class Universe:
    """Instrument Master — the single registry of trading instruments.

    Usage::

        from services.market_data.universe import universe

        universe.get("159852")       # → Instrument or None
        universe.all()               # → list[Instrument] (all 11)
        universe.enabled()           # → list[Instrument] (enabled only)
        universe.by_exchange(SSE)    # → filtered by exchange
    """

    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = {}
        self._register_seed()

    def _register_seed(self) -> None:
        """Register the 11 seed symbols."""
        for item in _SEED_DATA:
            inst = Instrument(
                symbol=item["symbol"],
                name=item["name"],
                exchange=item["exchange"],
                instrument_type=item["instrument_type"],
            )
            self._instruments[inst.symbol] = inst

    def get(self, symbol: str) -> Optional[Instrument]:
        """Look up an instrument by symbol.  Returns None if unknown."""
        return self._instruments.get(symbol)

    def all(self) -> list[Instrument]:
        """Return all registered instruments (including disabled)."""
        return list(self._instruments.values())

    def enabled(self) -> list[Instrument]:
        """Return only enabled instruments."""
        return [i for i in self._instruments.values() if i.enabled]

    def by_exchange(self, exchange: Exchange) -> list[Instrument]:
        """Filter instruments by exchange."""
        return [
            i for i in self._instruments.values() if i.exchange == exchange
        ]

    def by_type(self, itype: InstrumentType) -> list[Instrument]:
        """Filter instruments by instrument type."""
        return [
            i
            for i in self._instruments.values()
            if i.instrument_type == itype
        ]

    def symbols(self) -> list[str]:
        """Return all registered symbol codes."""
        return list(self._instruments.keys())

    def contains(self, symbol: str) -> bool:
        """Check whether a symbol is registered."""
        return symbol in self._instruments

    @property
    def count(self) -> int:
        return len(self._instruments)

    def as_list(self) -> list[dict]:
        """Serializable representation for API responses."""
        return [
            {
                "symbol": i.symbol,
                "name": i.name,
                "exchange": i.exchange.value,
                "instrument_type": i.instrument_type.value,
                "currency": i.currency,
                "lot_size": i.lot_size,
                "tick_size": str(i.tick_size),
                "trading_status": i.trading_status.value,
                "enabled": i.enabled,
            }
            for i in self._instruments.values()
        ]


# ── Singleton ─────────────────────────────────────────────────
universe = Universe()

__all__ = ["universe", "Universe"]
