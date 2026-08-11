"""
Index Normalizer — converts raw market index data into CanonicalIndex.

Supports global indices: S&P 500, NASDAQ Composite, DJIA, FTSE 100,
Nikkei 225, Hang Seng, CSI 300, VIX, etc.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalIndex,
    CanonicalMarketData,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class IndexNormalizer:
    """
    Normalizes raw index data from any provider into CanonicalIndex.

    Supports index data from Bloomberg, Reuters, exchange APIs,
    and other financial data providers.
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalIndex]:
        try:
            index = CanonicalIndex(
                event_type=MarketDataEventType.INDEX,
                asset_class=AssetClass.INDEX,
                instrument_id=self._extract_str(raw_data, "instrument_id", "index_id", "ticker"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "ticker", "symbol"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "ticker", "symbol"),

                index_value=self._to_decimal(raw_data, "index_value", "value", "last", "close", "price"),
                change=self._to_decimal(raw_data, "change", "net_change", "chg"),
                change_pct=self._to_decimal(raw_data, "change_pct", "pct_change", "pct_chg", "changePercent"),
                high=self._to_decimal(raw_data, "high", "highPrice", "h"),
                low=self._to_decimal(raw_data, "low", "lowPrice", "l"),
                open=self._to_decimal(raw_data, "open", "openPrice", "o"),
                previous_close=self._to_decimal(raw_data, "previous_close", "prevClose", "pc"),

                constituent_count=raw_data.get("constituent_count", 0),
                divisor=self._to_optional_decimal(raw_data, "divisor"),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "T"),
                received_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            index.normalized_timestamp_ns = self._now_ns()
            return index

        except Exception:
            logger.exception("Index normalization failed")
            return None

    # ── Helpers ────────────────────────────────────

    @staticmethod
    def _extract_str(data: dict[str, Any], *keys: str) -> str:
        for k in keys:
            if k in data and data[k] is not None:
                return str(data[k])
        return ""

    @staticmethod
    def _to_decimal(data: dict[str, Any], *keys: str) -> Decimal:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    return Decimal(str(data[k]))
                except Exception:
                    return Decimal("0")
        return Decimal("0")

    @staticmethod
    def _to_optional_decimal(data: dict[str, Any], *keys: str) -> Optional[Decimal]:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    return Decimal(str(data[k]))
                except Exception:
                    return None
        return None

    @staticmethod
    def _extract_timestamp_ns(data: dict[str, Any], *keys: str) -> int:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    val = data[k]
                    if isinstance(val, int) and val > 1e15:
                        return val
                    if isinstance(val, int) and val > 1e12:
                        return val * 1_000_000
                    if isinstance(val, (int, float)) and val < 1e11:
                        return int(val * 1e9)
                    return int(val)
                except Exception:
                    pass
        return 0

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
