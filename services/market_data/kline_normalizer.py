"""
K-Line Normalizer — converts raw candlestick/kline data into CanonicalKLine.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalKLine,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class KLineNormalizer:
    """Normalizes raw kline/candlestick data into CanonicalKLine."""

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalKLine]:
        try:
            # Handle Binance-style array kline [open_time, open, high, low, close, volume, ...]
            kline_array = raw_data.get("kline") or raw_data.get("candle")
            if isinstance(kline_array, list) and len(kline_array) >= 6:
                kline = CanonicalKLine(
                    event_type=MarketDataEventType.KLINE,
                    asset_class=self._infer_asset_class(raw_data),
                    instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                    canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol"),
                    exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                    exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                    original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                    open=Decimal(str(kline_array[1])),
                    high=Decimal(str(kline_array[2])),
                    low=Decimal(str(kline_array[3])),
                    close=Decimal(str(kline_array[4])),
                    volume=Decimal(str(kline_array[5])),
                    turnover=Decimal(str(kline_array[7])) if len(kline_array) > 7 else Decimal("0"),

                    interval=self._extract_str(raw_data, "interval", "i", "period"),
                    bar_open_timestamp_ns=self._extract_ts_from_val(kline_array[0]),
                    bar_close_timestamp_ns=self._extract_ts_from_val(kline_array[6]) if len(kline_array) > 6 else 0,
                    number_of_trades=int(kline_array[8]) if len(kline_array) > 8 else 0,
                    taker_buy_volume=Decimal(str(kline_array[9])) if len(kline_array) > 9 else Decimal("0"),
                    taker_buy_turnover=Decimal(str(kline_array[10])) if len(kline_array) > 10 else Decimal("0"),

                    is_closed=bool(raw_data.get("is_closed", raw_data.get("x", True))),

                    event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E"),
                    exchange_timestamp_ns=self._extract_ts_from_val(kline_array[6]) if len(kline_array) > 6 else 0,
                    received_timestamp_ns=self._now_ns(),
                    normalized_timestamp_ns=self._now_ns(),

                    quality=DataQuality.UNKNOWN,
                    source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                    source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                    source_raw=raw_data,
                    metadata=raw_data.get("metadata", {}),
                )
            else:
                # Object-style kline
                kline = CanonicalKLine(
                    event_type=MarketDataEventType.KLINE,
                    asset_class=self._infer_asset_class(raw_data),
                    instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                    canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol"),
                    exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                    exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                    original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                    open=self._to_decimal(raw_data, "open", "o"),
                    high=self._to_decimal(raw_data, "high", "h"),
                    low=self._to_decimal(raw_data, "low", "l"),
                    close=self._to_decimal(raw_data, "close", "c"),
                    volume=self._to_decimal(raw_data, "volume", "v", "vol"),
                    turnover=self._to_decimal(raw_data, "turnover", "quote_volume", "qv", "q"),

                    interval=self._extract_str(raw_data, "interval", "i", "period"),
                    bar_open_timestamp_ns=self._extract_timestamp_ns(raw_data, "open_time", "t", "start"),
                    bar_close_timestamp_ns=self._extract_timestamp_ns(raw_data, "close_time", "T", "end"),
                    number_of_trades=self._extract_int(raw_data, "trades", "n", "count"),
                    taker_buy_volume=self._to_decimal(raw_data, "taker_buy_volume", "tbv"),
                    taker_buy_turnover=self._to_decimal(raw_data, "taker_buy_turnover", "tbt"),

                    is_closed=bool(raw_data.get("is_closed", raw_data.get("x", True))),

                    event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E"),
                    exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "close_time", "T"),
                    received_timestamp_ns=self._now_ns(),
                    normalized_timestamp_ns=self._now_ns(),

                    quality=DataQuality.UNKNOWN,
                    source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                    source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                    source_raw=raw_data,
                    metadata=raw_data.get("metadata", {}),
                )

            # Derived fields
            if kline.open and kline.close:
                kline.change = kline.close - kline.open
                if kline.open != Decimal("0"):
                    kline.change_pct = (kline.change / kline.open) * Decimal("100")

            return kline

        except Exception:
            logger.exception("KLine normalization failed")
            return None

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
    def _extract_int(data: dict[str, Any], *keys: str) -> int:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    return int(data[k])
                except Exception:
                    return 0
        return 0

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
                    if isinstance(val, (int, float)):
                        return int(val * 1e9)
                except Exception:
                    pass
        return 0

    @staticmethod
    def _extract_ts_from_val(val: Any) -> int:
        try:
            if isinstance(val, int):
                if val > 1e15:
                    return val
                if val > 1e12:
                    return val * 1_000_000
                return val * 1_000_000_000
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
            "equity": AssetClass.EQUITY, "crypto": AssetClass.CRYPTO,
            "futures": AssetClass.FUTURES, "fx": AssetClass.FX,
            "index": AssetClass.INDEX,
        }
        return mapping.get(str(ac).lower(), AssetClass.OTHER)
