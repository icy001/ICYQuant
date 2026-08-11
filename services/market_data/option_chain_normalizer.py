"""
Option Chain Normalizer — converts raw option chain data into CanonicalOptionChain.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalOptionChain,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class OptionChainNormalizer:
    """Normalizes raw option chain data into CanonicalOptionChain."""

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalOptionChain]:
        try:
            chain = CanonicalOptionChain(
                event_type=MarketDataEventType.OPTION_CHAIN,
                asset_class=AssetClass.OPTION,
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                underlying_instrument_id=self._extract_str(raw_data, "underlying_id", "underlying"),
                underlying_price=self._to_decimal(raw_data, "underlying_price", "spot_price", "underlyingPrice"),
                expiration_date=self._extract_str(raw_data, "expiration_date", "expiry", "expiration"),
                strike_price=self._to_decimal(raw_data, "strike_price", "strike", "K"),
                option_type=self._extract_str(raw_data, "option_type", "type", "right", "opt_type"),
                option_style=self._extract_str(raw_data, "option_style", "style", "exercise_style"),

                delta=self._extract_optional_float(raw_data, "delta", "d"),
                gamma=self._extract_optional_float(raw_data, "gamma", "g"),
                theta=self._extract_optional_float(raw_data, "theta", "th"),
                vega=self._extract_optional_float(raw_data, "vega", "v"),
                rho=self._extract_optional_float(raw_data, "rho", "r"),
                implied_volatility=self._extract_optional_float(raw_data, "implied_volatility", "iv", "impliedVol"),

                bid=self._to_decimal(raw_data, "bid", "b", "bidPrice"),
                ask=self._to_decimal(raw_data, "ask", "a", "askPrice"),
                last=self._to_decimal(raw_data, "last", "price", "p", "lastPrice"),
                volume=self._to_decimal(raw_data, "volume", "v", "vol"),
                open_interest=self._to_decimal(raw_data, "open_interest", "oi", "openInterest"),

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

            # Normalize option type
            ot = chain.option_type.lower()
            if ot in ("call", "c"):
                chain.option_type = "call"
            elif ot in ("put", "p"):
                chain.option_type = "put"

            return chain

        except Exception:
            logger.exception("OptionChain normalization failed")
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
    def _extract_optional_float(data: dict[str, Any], *keys: str) -> Optional[float]:
        for k in keys:
            if k in data and data[k] is not None:
                try:
                    return float(data[k])
                except Exception:
                    pass
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
                    if isinstance(val, (int, float)):
                        return int(val * 1e9)
                except Exception:
                    pass
        return 0

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
