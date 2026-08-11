"""
Tick Normalizer — converts raw tick data into CanonicalTick.

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
    CanonicalTick,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class TickNormalizer:
    """
    Normalizes raw tick data from any exchange into CanonicalTick.

    Handles field name variations across exchanges (Binance, OKX,
    Bybit, Kraken, Coinbase, NYSE, NASDAQ, etc.).
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalTick]:
        try:
            tick = CanonicalTick(
                event_type=MarketDataEventType.TICK,
                asset_class=self._infer_asset_class(raw_data),
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol", "s"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                bid=self._to_decimal(raw_data, "bid", "b", "bidPrice", "bp"),
                ask=self._to_decimal(raw_data, "ask", "a", "askPrice", "ap"),
                last=self._to_decimal(raw_data, "last", "price", "p", "lastPrice", "lp"),
                bid_size=self._to_decimal(raw_data, "bid_size", "bidQty", "bs", "B"),
                ask_size=self._to_decimal(raw_data, "ask_size", "askQty", "as", "A"),
                last_size=self._to_decimal(raw_data, "last_size", "lastQty", "ls", "Q"),
                volume=self._to_decimal(raw_data, "volume", "v", "vol"),
                turnover=self._to_decimal(raw_data, "turnover", "quote_volume", "qv", "q"),
                open_interest=self._to_decimal(raw_data, "open_interest", "oi"),

                tick_direction=self._extract_str(raw_data, "tick_direction", "direction", "tickDir"),
                tick_sequence=self._extract_int(raw_data, "tick_sequence", "sequence", "seq"),
                condition_codes=self._extract_list(raw_data, "condition_codes", "conditions", "cond"),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "T", "trade_time"),
                received_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            # Derived fields
            if tick.bid and tick.ask:
                tick.spread = tick.ask - tick.bid
                tick.mid = (tick.bid + tick.ask) / Decimal("2")

            tick.normalized_timestamp_ns = self._now_ns()
            return tick

        except Exception:
            logger.exception("Tick normalization failed")
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
    def _extract_int(data: dict[str, Any], *keys: str) -> int:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    return int(data[k])
                except Exception:
                    return 0
        return 0

    @staticmethod
    def _extract_list(data: dict[str, Any], *keys: str) -> list[str]:
        for k in keys:
            if k in data and data[k] is not None:
                val = data[k]
                if isinstance(val, list):
                    return [str(v) for v in val]
                return [str(val)]
        return []

    @staticmethod
    def _extract_timestamp_ns(data: dict[str, Any], *keys: str) -> int:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    val = data[k]
                    # Already nanoseconds
                    if isinstance(val, int) and val > 1e15:
                        return val
                    # Milliseconds → nanoseconds
                    if isinstance(val, int) and val > 1e12:
                        return val * 1_000_000
                    # Seconds → nanoseconds
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
