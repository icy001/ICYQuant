"""
Trade Normalizer — converts raw trade/execution data into CanonicalTrade.

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
    CanonicalTrade,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class TradeNormalizer:
    """
    Normalizes raw trade (execution) data from any exchange into
    CanonicalTrade.

    Handles field name variations across exchanges.
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalTrade]:
        try:
            trade = CanonicalTrade(
                event_type=MarketDataEventType.TRADE,
                asset_class=self._infer_asset_class(raw_data),
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol", "s"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                price=self._to_decimal(raw_data, "price", "p", "trade_price", "tp"),
                quantity=self._to_decimal(raw_data, "quantity", "q", "qty", "size", "volume"),
                trade_id=self._extract_str(raw_data, "trade_id", "tid", "tradeId", "a"),
                trade_side=self._extract_str(raw_data, "trade_side", "side", "isBuyerMaker", "S"),
                trade_type=self._extract_str(raw_data, "trade_type", "type", "tradeType"),
                is_reported=raw_data.get("is_reported", False),
                accumulated_volume=self._to_decimal(raw_data, "accumulated_volume", "acc_vol"),
                vwap=self._to_decimal(raw_data, "vwap", "VWAP"),

                buyer_id=self._extract_str(raw_data, "buyer_id", "buyer"),
                seller_id=self._extract_str(raw_data, "seller_id", "seller"),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts", "T"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "trade_time"),
                received_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            trade.normalized_timestamp_ns = self._now_ns()
            return trade

        except Exception:
            logger.exception("Trade normalization failed")
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
