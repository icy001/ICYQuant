"""
Crypto Normalizer — converts raw cryptocurrency market data into
CanonicalCrypto.

Supports major exchanges: Binance, OKX, Bybit, Coinbase, Kraken, etc.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalCrypto,
    CanonicalMarketData,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class CryptoNormalizer:
    """
    Normalizes raw crypto market data from any exchange into CanonicalCrypto.

    Handles field name variations across major crypto exchanges
    (Binance, OKX, Bybit, Kraken, Coinbase, Huobi, KuCoin, etc.).
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalCrypto]:
        try:
            crypto = CanonicalCrypto(
                event_type=MarketDataEventType.CRYPTO,
                asset_class=AssetClass.CRYPTO,
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol", "s"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                base_asset=self._extract_str(raw_data, "base_asset", "baseAsset", "base"),
                quote_asset=self._extract_str(raw_data, "quote_asset", "quoteAsset", "quote"),
                last=self._to_decimal(raw_data, "last", "price", "p", "lastPrice", "c"),
                bid=self._to_decimal(raw_data, "bid", "b", "bidPrice", "bp"),
                ask=self._to_decimal(raw_data, "ask", "a", "askPrice", "ap"),
                volume=self._to_decimal(raw_data, "volume", "v", "vol"),
                turnover=self._to_decimal(raw_data, "turnover", "quote_volume", "qv", "q"),
                high_24h=self._to_decimal(raw_data, "high_24h", "highPrice", "h", "high"),
                low_24h=self._to_decimal(raw_data, "low_24h", "lowPrice", "l", "low"),
                change_24h=self._to_decimal(raw_data, "change_24h", "priceChange", "P"),
                change_pct_24h=self._to_decimal(raw_data, "change_pct_24h", "priceChangePercent", "P"),

                exchange_product_code=self._extract_str(raw_data, "exchange_product_code", "product_code"),
                is_margin_enabled=raw_data.get("is_margin_enabled", False),
                is_spot=raw_data.get("is_spot", True),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "T", "trade_time"),
                received_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            crypto.normalized_timestamp_ns = self._now_ns()
            return crypto

        except Exception:
            logger.exception("Crypto normalization failed")
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
