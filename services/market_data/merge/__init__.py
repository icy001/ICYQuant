"""Historical + Real-time Merge (Commit 008).

Import surface::

    from services.market_data.merge import (
        BarMergeEngine, merge_engine,      # engine + singleton
        MergePolicy, MergeDecision,        # policy
        BarRevision,                       # closed-bar audit record
        SyntheticHistoricalProvider,       # Phase 1 history source
        HISTORICAL, REALTIME,              # per-bar source tags
    )

Architecture::

    Historical Provider        BarService (realtime)
             └────────────┬────────────┘
                          ▼
                    merge_engine
                          ▼
              Unified 1m Series  →  cache / API / Dashboard

Redis stays a cache, never the source of truth (§13).
"""
from __future__ import annotations

from .bar_merge import HISTORICAL, REALTIME, BarMergeEngine
from .historical_provider import SyntheticHistoricalProvider
from .merge_policy import BarRevision, MergeDecision, MergePolicy

__all__ = [
    "BarMergeEngine",
    "MergePolicy",
    "MergeDecision",
    "BarRevision",
    "SyntheticHistoricalProvider",
    "HISTORICAL",
    "REALTIME",
    "merge_engine",
]


def _build_default_engine() -> BarMergeEngine:
    """Wire the singleton lazily to avoid import cycles."""
    from ..aggregation.bar_service import bar_service
    from ..cache import market_cache

    return BarMergeEngine(
        SyntheticHistoricalProvider(),
        bar_service=bar_service,
        market_cache=market_cache,
    )


merge_engine: BarMergeEngine = _build_default_engine()
