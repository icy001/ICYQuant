"""Market cache package — shared latest market state (Commit 007).

The Redis Market Cache holds only the latest quality-passed market
state (quote / bar / session / quality) with session-aware TTLs.
History and research data never live here — that is the job of
PostgreSQL / Parquet / object storage.

Import surface::

    from services.market_data.cache import (
        MarketCache, market_cache,       # service + singleton
        CacheConfig, CacheState,          # config + state enum
        CacheBackendError,                # backend failure type
        quote_key, bar_key,               # fixed key convention
        session_key, quality_key,
        quote_pattern,                     # quote-key inventory glob
    )
"""
from __future__ import annotations

from .cache_models import (
    CacheBackendError,
    CacheConfig,
    CacheState,
)
from .market_cache import MarketCache, market_cache
from .redis_keys import (
    bar_key,
    quote_key,
    quote_pattern,
    quality_key,
    session_key,
)

__all__ = [
    "MarketCache",
    "market_cache",
    "CacheConfig",
    "CacheState",
    "CacheBackendError",
    "quote_key",
    "bar_key",
    "session_key",
    "quality_key",
    "quote_pattern",
]
