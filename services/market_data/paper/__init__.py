"""Paper Market Feed package — real market data for Paper Trading
(Commit 009).

Import surface::

    from services.market_data.paper import (
        PaperMarketFeed, paper_market_feed,   # feed + singleton
        PaperFeedConfig,                      # config
        PaperFeedState,                       # READY/DEGRADED/BLOCKED/OFFLINE
        FillPriceSource,                      # ASK/BID/LAST provenance
        PaperFeedError,                       # §17 reason codes
        PaperBlockedError,                    # raised block
        PaperOrderDecision, PaperFill,        # verdict + simulated fill
        DISCLAIMER,                           # "PAPER — NO REAL MONEY"
    )

Paper Trading no longer simulates prices.  It consumes the real
pipeline (adapter → quotes → bars → session → quality gate → cache →
merge) and only *simulates the fill*::

    quote_service / bar_service / merge_engine / market_cache
                          ↓
                  PaperMarketFeed
                          ↓
    PaperTradingSession (existing engine, unchanged)
"""
from __future__ import annotations

from .paper_feed_config import PaperFeedConfig
from .paper_feed_state import (
    FillPriceSource,
    PaperBlockedError,
    PaperFeedError,
    PaperFeedState,
    PaperFill,
    PaperOrderDecision,
)
from .paper_market_feed import (
    DISCLAIMER,
    PaperMarketFeed,
    paper_market_feed,
)

__all__ = [
    "PaperMarketFeed",
    "paper_market_feed",
    "PaperFeedConfig",
    "PaperFeedState",
    "FillPriceSource",
    "PaperFeedError",
    "PaperBlockedError",
    "PaperOrderDecision",
    "PaperFill",
    "DISCLAIMER",
]
