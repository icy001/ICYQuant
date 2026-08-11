"""
Symbol Mapper — maps exchange-specific symbols to canonical instrument
identifiers across all supported exchanges and asset classes.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SymbolMapping:
    """A single symbol mapping record."""

    original_symbol: str = ""
    exchange_id: str = ""
    exchange_code: str = ""
    canonical_symbol: str = ""
    instrument_id: str = ""
    asset_class: str = ""
    currency: str = "USD"
    tick_size: float = 0.0
    lot_size: float = 0.0
    is_active: bool = True

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SymbolMappingRegistry:
    """Registry of all symbol mappings."""

    mappings: dict[str, SymbolMapping] = field(default_factory=dict)

    def add(self, mapping: SymbolMapping) -> None:
        key = f"{mapping.exchange_id}:{mapping.original_symbol}"
        self.mappings[key] = mapping

    def get(self, exchange_id: str, symbol: str) -> Optional[SymbolMapping]:
        key = f"{exchange_id}:{symbol}"
        return self.mappings.get(key)

    def remove(self, exchange_id: str, symbol: str) -> None:
        key = f"{exchange_id}:{symbol}"
        self.mappings.pop(key, None)

    def find_by_canonical(self, canonical_symbol: str) -> list[SymbolMapping]:
        return [m for m in self.mappings.values() if m.canonical_symbol == canonical_symbol]

    @property
    def count(self) -> int:
        return len(self.mappings)


class SymbolMapper:
    """
    Maps exchange-specific symbols to canonical instrument identifiers.

    Resolves chains like:
        AAPL.US → NASDAQ:AAPL → US.AAPL → Canonical Instrument ID

    Supports all asset classes across equities, futures, options,
    FX, crypto, and indices.
    """

    def __init__(self) -> None:
        self._registry = SymbolMappingRegistry()
        self._alias_map: dict[str, str] = {}

    async def initialize(self) -> None:
        logger.info("SymbolMapper initialized with %d mappings", self._registry.count)

    # ── Core mapping ───────────────────────────────

    async def map_to_canonical(
        self, symbol: str, exchange_id: str = "", asset_class: str = ""
    ) -> Optional[SymbolMapping]:
        """Resolve an exchange symbol to its canonical form."""

        # Try exact match
        mapping = self._registry.get(exchange_id, symbol)
        if mapping:
            return mapping

        # Try alias resolution
        alias_key = f"{exchange_id}:{symbol}"
        if alias_key in self._alias_map:
            return self._registry.get(exchange_id, self._alias_map[alias_key])

        return None

    async def register_mapping(
        self,
        original_symbol: str,
        exchange_id: str,
        canonical_symbol: str,
        instrument_id: str = "",
        asset_class: str = "",
        **kwargs: Any,
    ) -> SymbolMapping:
        """Register a new symbol mapping."""

        mapping = SymbolMapping(
            original_symbol=original_symbol,
            exchange_id=exchange_id,
            exchange_code=exchange_id,
            canonical_symbol=canonical_symbol,
            instrument_id=instrument_id or canonical_symbol,
            asset_class=asset_class,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            **kwargs,
        )
        self._registry.add(mapping)
        logger.debug("Registered mapping: %s → %s", original_symbol, canonical_symbol)
        return mapping

    async def register_alias(self, exchange_id: str, alias: str, canonical_symbol: str) -> None:
        """Register an alias for a symbol (e.g. BRK.B → BRK_B)."""
        self._alias_map[f"{exchange_id}:{alias}"] = canonical_symbol

    async def resolve_batch(
        self, symbols: list[tuple[str, str]]
    ) -> dict[tuple[str, str], Optional[SymbolMapping]]:
        """Batch-resolve multiple symbols."""
        return {
            (sym, ex): await self.map_to_canonical(sym, ex)
            for sym, ex in symbols
        }

    async def get_all_for_exchange(self, exchange_id: str) -> list[SymbolMapping]:
        """Get all mappings for a given exchange."""
        return [m for m in self._registry.mappings.values() if m.exchange_id == exchange_id]

    @property
    def mapping_count(self) -> int:
        return self._registry.count
