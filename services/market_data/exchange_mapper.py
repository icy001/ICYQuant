"""
Exchange Mapper — normalizes exchange identifiers across all venues
into canonical exchange IDs.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExchangeMapping:
    """Mapping from raw exchange identifier to canonical form."""

    exchange_id: str = ""          # Canonical exchange ID (e.g., "NASDAQ")
    exchange_code: str = ""        # MIC code (e.g., "XNAS")
    exchange_name: str = ""        # Full name
    country: str = ""              # ISO 3166-1 alpha-2
    timezone: str = "UTC"          # IANA timezone
    asset_classes: list[str] = field(default_factory=list)
    is_active: bool = True

    trading_hours_start: str = "09:30"
    trading_hours_end: str = "16:00"
    trading_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])

    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExchangeMapper:
    """
    Maps raw exchange identifiers to canonical exchange IDs.

    Normalizes across naming conventions:
        NASDAQ / XNAS / Nasdaq / nasdaq → NASDAQ
        NYSE / XNYS / NYSE American → NYSE
        CME / XCME → CME
        HKEX / XHKG → HKEX
        Binance / BinanceUS → Binance
    """

    def __init__(self) -> None:
        self._mappings: dict[str, ExchangeMapping] = {}
        self._alias_map: dict[str, str] = {}
        self._mic_map: dict[str, str] = {}

    async def initialize(self) -> None:
        logger.info("ExchangeMapper initialized with %d exchanges", len(self._mappings))

    # ── Core mapping ───────────────────────────────

    async def map_to_canonical(self, raw_exchange: str) -> Optional[ExchangeMapping]:
        """Resolve any exchange identifier to its canonical form."""

        key = raw_exchange.strip().upper()

        # Direct match
        if key in self._mappings:
            return self._mappings[key]

        # Alias resolution
        if key in self._alias_map:
            return self._mappings.get(self._alias_map[key])

        # MIC code match
        if key in self._mic_map:
            return self._mappings.get(self._mic_map[key])

        # Case-insensitive name search
        for mapping in self._mappings.values():
            if mapping.exchange_name.strip().upper() == key:
                return mapping

        return None

    async def register_exchange(
        self,
        exchange_id: str,
        exchange_code: str = "",
        exchange_name: str = "",
        country: str = "",
        timezone: str = "UTC",
        asset_classes: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> ExchangeMapping:
        """Register a canonical exchange mapping."""

        mapping = ExchangeMapping(
            exchange_id=exchange_id,
            exchange_code=exchange_code or exchange_id,
            exchange_name=exchange_name or exchange_id,
            country=country,
            timezone=timezone,
            asset_classes=asset_classes or [],
            created_at=datetime.now(timezone.utc),
            **kwargs,
        )
        self._mappings[exchange_id.upper()] = mapping
        self._mappings[exchange_code.upper()] = mapping
        if exchange_name:
            self._mappings[exchange_name.upper()] = mapping

        logger.debug("Registered exchange: %s (%s)", exchange_id, exchange_code)
        return mapping

    async def register_alias(self, alias: str, canonical_id: str) -> None:
        """Register an alias for an exchange."""
        self._alias_map[alias.strip().upper()] = canonical_id.upper()

    async def register_mic(self, mic_code: str, canonical_id: str) -> None:
        """Register a MIC code mapping."""
        self._mic_map[mic_code.strip().upper()] = canonical_id.upper()

    async def get_all_active(self) -> list[ExchangeMapping]:
        """Get all active exchange mappings."""
        seen: set[str] = set()
        result: list[ExchangeMapping] = []
        for m in self._mappings.values():
            if m.is_active and m.exchange_id not in seen:
                seen.add(m.exchange_id)
                result.append(m)
        return result

    async def get_by_country(self, country: str) -> list[ExchangeMapping]:
        """Get exchanges for a given country."""
        country_upper = country.strip().upper()
        seen: set[str] = set()
        result: list[ExchangeMapping] = []
        for m in self._mappings.values():
            if m.country.upper() == country_upper and m.exchange_id not in seen:
                seen.add(m.exchange_id)
                result.append(m)
        return result

    @property
    def exchange_count(self) -> int:
        seen: set[str] = {m.exchange_id for m in self._mappings.values()}
        return len(seen)
