"""
Market Data Normalizer — central dispatcher that routes raw market data
to the appropriate asset-class-specific normalizer.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .canonical_model import CanonicalMarketData, MarketDataEventType
from .crypto_normalizer import CryptoNormalizer
from .futures_normalizer import FuturesNormalizer
from .fx_normalizer import FXNormalizer
from .index_normalizer import IndexNormalizer
from .kline_normalizer import KLineNormalizer
from .option_chain_normalizer import OptionChainNormalizer
from .orderbook_normalizer import OrderBookNormalizer
from .quote_normalizer import QuoteNormalizer
from .tick_normalizer import TickNormalizer
from .trade_normalizer import TradeNormalizer

logger = logging.getLogger(__name__)


class MarketDataNormalizer:
    """
    Central normalizer that dispatches raw data to the correct
    asset-class or event-type specific normalizer.

    All raw data enters here, is classified, and then routed
    to the appropriate specialized normalizer for conversion
    into the Canonical Market Data Model.
    """

    def __init__(self) -> None:
        self._normalizers: dict[MarketDataEventType, Any] = {}

    async def initialize(self) -> None:
        self._normalizers = {
            MarketDataEventType.TICK: TickNormalizer(),
            MarketDataEventType.TRADE: TradeNormalizer(),
            MarketDataEventType.QUOTE: QuoteNormalizer(),
            MarketDataEventType.ORDER_BOOK: OrderBookNormalizer(),
            MarketDataEventType.KLINE: KLineNormalizer(),
            MarketDataEventType.OPTION_CHAIN: OptionChainNormalizer(),
            MarketDataEventType.FUTURES: FuturesNormalizer(),
            MarketDataEventType.FX: FXNormalizer(),
            MarketDataEventType.CRYPTO: CryptoNormalizer(),
            MarketDataEventType.INDEX: IndexNormalizer(),
        }
        logger.info("MarketDataNormalizer initialized with %d normalizers", len(self._normalizers))

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalMarketData]:
        """
        Classify and normalize raw market data.

        Classification strategy:
        1. Explicit event_type field in raw_data
        2. Heuristic: check field patterns (e.g., 'bids'/'asks' → orderbook)
        3. Default to tick normalizer
        """
        event_type = self._classify(raw_data)
        normalizer = self._normalizers.get(event_type)

        if normalizer is None:
            logger.warning("No normalizer for event_type=%s, falling back to tick", event_type)
            normalizer = self._normalizers.get(MarketDataEventType.TICK)

        if normalizer is None:
            return None

        try:
            return await normalizer.normalize(raw_data)
        except Exception:
            logger.exception("Normalizer failed for event_type=%s", event_type)
            return None

    def _classify(self, raw_data: dict[str, Any]) -> MarketDataEventType:
        # Explicit type field
        raw_type = raw_data.get("event_type") or raw_data.get("type") or raw_data.get("e")
        if raw_type:
            type_map = {
                "tick": MarketDataEventType.TICK,
                "trade": MarketDataEventType.TRADE,
                "quote": MarketDataEventType.QUOTE,
                "orderbook": MarketDataEventType.ORDER_BOOK,
                "order_book": MarketDataEventType.ORDER_BOOK,
                "depth": MarketDataEventType.ORDER_BOOK,
                "kline": MarketDataEventType.KLINE,
                "candle": MarketDataEventType.KLINE,
                "option_chain": MarketDataEventType.OPTION_CHAIN,
                "option": MarketDataEventType.OPTION_CHAIN,
                "futures": MarketDataEventType.FUTURES,
                "fx": MarketDataEventType.FX,
                "forex": MarketDataEventType.FX,
                "crypto": MarketDataEventType.CRYPTO,
                "index": MarketDataEventType.INDEX,
            }
            matched = type_map.get(str(raw_type).lower())
            if matched:
                return matched

        # Heuristic classification
        if "bids" in raw_data and "asks" in raw_data:
            return MarketDataEventType.ORDER_BOOK
        if "candle" in raw_data or "ohlcv" in raw_data or "kline" in raw_data:
            return MarketDataEventType.KLINE
        if "strike" in raw_data or "option_type" in raw_data:
            return MarketDataEventType.OPTION_CHAIN
        if "base_currency" in raw_data:
            return MarketDataEventType.FX
        if "funding_rate" in raw_data:
            return MarketDataEventType.FUTURES

        # Default
        return MarketDataEventType.TICK

    def register_normalizer(
        self, event_type: MarketDataEventType, normalizer: Any
    ) -> None:
        self._normalizers[event_type] = normalizer

    def _now_ns(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
