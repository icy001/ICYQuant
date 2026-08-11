"""
Quote Normalizer — converts raw quote data into CanonicalQuote.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalMarketData,
    CanonicalQuote,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class QuoteNormalizer:
    """
    Normalizes raw quote (best bid/ask) data from any exchange
    into CanonicalQuote.

    Handles field name variations across exchanges.
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalQuote]:
        try:
            quote = CanonicalQuote(
                event_type=MarketDataEventType.QUOTE,
                asset_class=self._infer_asset_class(raw_data),
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol", "s"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                bid=self._to_decimal(raw_data, "bid", "b", "bidPrice", "bp"),
                ask=self._to_decimal(raw_data, "ask", "a", "askPrice", "ap"),
                bid_size=self._to_decimal(raw_data, "bid_size", "bidQty", "bs", "B"),
                ask_size=self._to_decimal(raw_data, "ask_size", "askQty", "as", "A"),
                bid_exchange=self._extract_str(raw_data, "bid_exchange", "bidExchange"),
                ask_exchange=self._extract_str(raw_data, "ask_exchange", "askExchange"),
                quote_condition=self._extract_str(raw_data, "quote_condition", "condition", "cond"),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "T"),
                received_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            if quote.bid and quote.ask:
                quote.spread = quote.ask - quote.bid
                quote.mid = (quote.bid + quote.ask) / Decimal("2")

            quote.normalized_timestamp_ns = self._now_ns()
            return quote

        except Exception:
            logger.exception("Quote normalization failed")
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

    @staticmethod
    def _infer_asset_class(raw_data: dict[str, Any]) -> AssetClass:
        ac = raw_data.get("asset_class", "")
        mapping = {
            "equity": AssetClass.EQUITY,
            "etf": AssetClass.ETF,
            "futures": AssetClass.FUTURES,
            "option": AssetClass.OPTION,
            "fx": AssetClass.FX,
            "crypto": AssetClass.CRYPTO,
            "index": AssetClass.INDEX,
            "bond": AssetClass.BOND,
            "commodity": AssetClass.COMMODITY,
        }
        return mapping.get(str(ac).lower(), AssetClass.OTHER)
