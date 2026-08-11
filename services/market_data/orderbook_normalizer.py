"""
Order Book Normalizer — converts raw order book / depth data into CanonicalOrderBook.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalOrderBook,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class OrderBookNormalizer:
    """
    Normalizes raw order book snapshots and depth updates into
    CanonicalOrderBook.

    Supports full book snapshots, incremental updates, and
    various exchange-specific depth formats.
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalOrderBook]:
        try:
            bids_raw = raw_data.get("bids", raw_data.get("b", []))
            asks_raw = raw_data.get("asks", raw_data.get("a", []))

            bids = self._parse_levels(bids_raw)
            asks = self._parse_levels(asks_raw)

            best_bid = bids[0][0] if bids else Decimal("0")
            best_ask = asks[0][0] if asks else Decimal("0")
            best_bid_size = bids[0][1] if bids else Decimal("0")
            best_ask_size = asks[0][1] if asks else Decimal("0")

            spread = best_ask - best_bid if best_bid and best_ask else Decimal("0")
            mid = (best_bid + best_ask) / Decimal("2") if best_bid and best_ask else Decimal("0")

            book = CanonicalOrderBook(
                event_type=MarketDataEventType.ORDER_BOOK,
                asset_class=self._infer_asset_class(raw_data),
                instrument_id=self._extract_str(raw_data, "instrument_id", "symbol", "s"),
                canonical_symbol=self._extract_str(raw_data, "canonical_symbol", "symbol"),
                exchange_id=self._extract_str(raw_data, "exchange_id", "exchange", "E"),
                exchange_code=self._extract_str(raw_data, "exchange_code", "exchange"),
                original_symbol=self._extract_str(raw_data, "original_symbol", "symbol", "s"),

                bids=bids,
                asks=asks,
                best_bid=best_bid,
                best_ask=best_ask,
                best_bid_size=best_bid_size,
                best_ask_size=best_ask_size,
                spread=spread,
                mid=mid,

                depth_levels=max(len(bids), len(asks)),
                is_snapshot=raw_data.get("is_snapshot", True),
                update_type=self._extract_str(raw_data, "update_type", "type", "event"),
                sequence_number=self._extract_int(raw_data, "sequence", "seq", "lastUpdateId", "u"),
                previous_sequence=self._extract_int(raw_data, "prev_sequence", "prev_seq", "pu"),

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

            return book

        except Exception:
            logger.exception("OrderBook normalization failed")
            return None

    @staticmethod
    def _parse_levels(levels: Any) -> list[tuple[Decimal, Decimal]]:
        """Parse price/quantity levels from various formats."""
        result: list[tuple[Decimal, Decimal]] = []
        if not levels:
            return result
        if not isinstance(levels, list):
            return result

        for level in levels:
            try:
                if isinstance(level, (list, tuple)) and len(level) >= 2:
                    price = Decimal(str(level[0]))
                    qty = Decimal(str(level[1]))
                    result.append((price, qty))
                elif isinstance(level, dict):
                    price = Decimal(str(level.get("price", level.get("p", 0))))
                    qty = Decimal(str(level.get("quantity", level.get("qty", level.get("q", 0)))))
                    result.append((price, qty))
            except Exception:
                continue
        return result

    @staticmethod
    def _extract_str(data: dict[str, Any], *keys: str) -> str:
        for k in keys:
            if k in data and data[k] is not None:
                return str(data[k])
        return ""

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
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)

    @staticmethod
    def _infer_asset_class(raw_data: dict[str, Any]) -> AssetClass:
        ac = raw_data.get("asset_class", "")
        mapping = {
            "equity": AssetClass.EQUITY, "crypto": AssetClass.CRYPTO,
            "futures": AssetClass.FUTURES, "fx": AssetClass.FX,
        }
        return mapping.get(str(ac).lower(), AssetClass.OTHER)
