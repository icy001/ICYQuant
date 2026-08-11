"""
Instrument Registry — centralized registry of all tradable instruments
across exchanges with lifecycle management.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InstrumentType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    FUTURES = "futures"
    OPTION = "option"
    FX_SPOT = "fx_spot"
    FX_FORWARD = "fx_forward"
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_PERPETUAL = "crypto_perpetual"
    INDEX = "index"
    BOND = "bond"
    WARRANT = "warrant"
    CFD = "cfd"
    OTHER = "other"


class InstrumentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELISTED = "delisted"
    EXPIRED = "expired"
    PRE_LISTING = "pre_listing"


@dataclass
class Instrument:
    """A single tradable instrument record."""

    instrument_id: str = ""
    canonical_symbol: str = ""
    exchange_id: str = ""
    instrument_type: InstrumentType = InstrumentType.OTHER
    asset_class: str = ""
    status: InstrumentStatus = InstrumentStatus.ACTIVE

    # Identifier chain
    isin: str = ""
    cusip: str = ""
    sedol: str = ""
    ric: str = ""
    bloomberg_ticker: str = ""

    # Contract details
    currency: str = "USD"
    tick_size: float = 0.0
    lot_size: float = 0.0
    multiplier: float = 1.0
    min_qty: float = 0.0
    max_qty: float = 0.0

    # Dates
    listing_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    delisting_date: Optional[datetime] = None

    # Underlying (for derivatives)
    underlying_instrument_id: str = ""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class InstrumentRegistry:
    """
    Centralized registry of all tradable instruments.

    Tracks instrument lifecycle (pre-listing → active → suspended →
    delisted/expired) and provides lookup by various identifiers.
    """

    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = {}
        self._by_isin: dict[str, str] = {}
        self._by_symbol: dict[str, list[str]] = {}
        self._by_exchange: dict[str, list[str]] = {}

    async def initialize(self) -> None:
        logger.info("InstrumentRegistry initialized with %d instruments", len(self._instruments))

    # ── CRUD ──────────────────────────────────────

    async def register(self, instrument: Instrument) -> Instrument:
        """Register a new instrument or update an existing one."""
        instrument.created_at = instrument.created_at or datetime.now(timezone.utc)
        instrument.updated_at = datetime.now(timezone.utc)

        self._instruments[instrument.instrument_id] = instrument

        # Index by ISIN
        if instrument.isin:
            self._by_isin[instrument.isin] = instrument.instrument_id

        # Index by symbol
        sym = instrument.canonical_symbol
        if sym not in self._by_symbol:
            self._by_symbol[sym] = []
        if instrument.instrument_id not in self._by_symbol[sym]:
            self._by_symbol[sym].append(instrument.instrument_id)

        # Index by exchange
        ex = instrument.exchange_id
        if ex not in self._by_exchange:
            self._by_exchange[ex] = []
        if instrument.instrument_id not in self._by_exchange[ex]:
            self._by_exchange[ex].append(instrument.instrument_id)

        logger.debug("Registered instrument: %s (%s)", instrument.instrument_id, instrument.canonical_symbol)
        return instrument

    async def get(self, instrument_id: str) -> Optional[Instrument]:
        """Get an instrument by its canonical ID."""
        return self._instruments.get(instrument_id)

    async def get_by_isin(self, isin: str) -> Optional[Instrument]:
        """Look up by ISIN."""
        inst_id = self._by_isin.get(isin)
        if inst_id:
            return self._instruments.get(inst_id)
        return None

    async def find_by_symbol(self, symbol: str) -> list[Instrument]:
        """Find all instruments with a given canonical symbol."""
        ids = self._by_symbol.get(symbol, [])
        return [self._instruments[i] for i in ids if i in self._instruments]

    async def find_by_exchange(self, exchange_id: str) -> list[Instrument]:
        """Get all instruments for an exchange."""
        ids = self._by_exchange.get(exchange_id, [])
        return [self._instruments[i] for i in ids if i in self._instruments]

    async def update_status(self, instrument_id: str, status: InstrumentStatus) -> bool:
        """Update an instrument's lifecycle status."""
        inst = self._instruments.get(instrument_id)
        if inst:
            inst.status = status
            inst.updated_at = datetime.now(timezone.utc)
            logger.info("Instrument %s status → %s", instrument_id, status.value)
            return True
        return False

    async def remove(self, instrument_id: str) -> bool:
        """Remove an instrument from the registry."""
        inst = self._instruments.pop(instrument_id, None)
        if inst:
            self._by_isin.pop(inst.isin, None)
            self._by_symbol.get(inst.canonical_symbol, []).remove(instrument_id)
            self._by_exchange.get(inst.exchange_id, []).remove(instrument_id)
            return True
        return False

    async def get_active(self) -> list[Instrument]:
        """Get all active instruments."""
        return [i for i in self._instruments.values() if i.status == InstrumentStatus.ACTIVE]

    @property
    def count(self) -> int:
        return len(self._instruments)

    @property
    def active_count(self) -> int:
        return sum(1 for i in self._instruments.values() if i.status == InstrumentStatus.ACTIVE)
