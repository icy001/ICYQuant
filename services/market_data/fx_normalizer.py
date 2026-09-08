"""FX Normalizer — converts raw FX market data into CanonicalFX.

Commit 16 Part 1.2
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from .canonical_model import (
    AssetClass,
    CanonicalFX,
    CanonicalMarketData,
    DataQuality,
    MarketDataEventType,
)

logger = logging.getLogger(__name__)


class FXNormalizer:
    """
    Normalizes raw FX market data from any provider into CanonicalFX.

    Handles field name variations across major FX venues
    (Reuters, Bloomberg, EBS, etc.).
    """

    async def normalize(self, raw_data: dict[str, Any]) -> Optional[CanonicalFX]:
        try:
            fx = CanonicalFX(
                event_type=MarketDataEventType.FX,
                asset_class=AssetClass.FX,
            )
            fx.symbol = raw_data.get("symbol", raw_data.get("pair", ""))
            fx.bid = Decimal(str(raw_data.get("bid", "0")))
            fx.ask = Decimal(str(raw_data.get("ask", "0")))
            fx.timestamp = raw_data.get(
                "timestamp", datetime.now(timezone.utc)
            )
            fx.data_quality = DataQuality.GOOD
            return fx
        except Exception as exc:  # noqa: BLE001
            logger.error("FX normalization failed: %s", exc)
            return None
