"""
Futures Normalizer — converts raw futures data into CanonicalFutures.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalFutures,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class FuturesNormalizer:
    """Normalizes raw futures contract data into CanonicalFutures."""

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalFutures]:
        try:
            futures = CanonicalFutures(
                event_type=MarketDataEventType.FUTURES,
                asset_class=AssetClass.FUTURES,
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                last=self._to_decimal(raw_data, "last", "price", "p", "lastPrice"),
                bid=self._to_decimal(raw_data, "bid", "b", "bidPrice"),
                ask=self._to_decimal(raw_data, "ask", "a", "askPrice"),
                volume=self._to_decimal(raw_data, "volume", "v", "vol"),
                turnover=self._to_decimal(raw_data, "turnover", "quote_volume", "qv"),
                open_interest=self._to_decimal(raw_data, "open_interest", "oi", "openInterest"),
                settlement_price=self._to_decimal(raw_data, "settlement_price", "settle", "settlement"),
                mark_price=self._to_decimal(raw_data, "mark_price", "mark", "markPrice"),
                funding_rate=self._to_decimal(raw_data, "funding_rate", "funding", "fr"),

                contract_code=self._extract_str(raw_data, "contract_code", "contract", "code"),
                expiry_date=self._extract_str(raw_data, "expiry_date", "expiry", "expiration", "delivery"),
                contract_type=self._extract_str(raw_data, "contract_type", "type", "ct"),
                multiplier=self._to_decimal(raw_data, "multiplier", "contract_multiplier", "m"),
                tick_size=self._to_decimal(raw_data, "tick_size", "tick", "ts"),

                event_timestamp_ns=self._extract_timestamp_ns(raw_data, "event_time", "E", "timestamp", "ts"),
                exchange_timestamp_ns=self._extract_timestamp_ns(raw_data, "exchange_time", "T"),
                received_timestamp_ns=self._now_ns(),
                normalized_timestamp_ns=self._now_ns(),

                quality=DataQuality.UNKNOWN,
                source_feed=self._extract_str(raw_data, "source_feed", "feed"),
                source_protocol=self._extract_str(raw_data, "source_protocol", "protocol"),
                source_raw=raw_data,
                metadata=raw_data.get("metadata", {}),
            )

            # Normalize contract type
            ct = futures.contract_type.lower()
            if ct in ("perpetual", "perp"):
                futures.contract_type = "perpetual"
            elif ct in ("quarterly", "quarter"):
                futures.contract_type = "quarterly"
            elif ct in ("delivery", "deliverable"):
                futures.contract_type = "delivery"

            return futures

        except Exception:
            logger.exception("Futures normalization failed")
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
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
