"""Paper Trading runtime adapters (Commit 009 §18).

Bridges the real market data pipeline into the existing Paper Trading
engine without building a second one::

    from apps.runtime.paper import (
        PaperMarketFeedAdapter,      # MarketFeed over real data
        RealMarketPaperSession,      # PaperTradingSession + real feed
    )
"""
from __future__ import annotations

from .market_feed_adapter import (
    DISCLAIMER,
    PaperMarketFeedAdapter,
    RealMarketPaperSession,
)

__all__ = [
    "PaperMarketFeedAdapter",
    "RealMarketPaperSession",
    "DISCLAIMER",
]
