"""Cache models — states, config, backend contract (Commit 007).

Redis is NOT a market data database.  It holds only the latest,
fast-to-access Market State that already passed the Quality Gate
(Commit 006).  History / research / audit data stay in PostgreSQL /
Parquet / object storage.

CacheState — the honest answer to "what does the cache hold for
this symbol right now?" (§7: quote age + trading session combined)::

    LIVE             continuous phase, quote age ≤ fresh threshold
    STALE            continuous phase, quote older than fresh
    MARKET_PAUSED    lunch break / auction / pre-open on a trading day
    MARKET_CLOSED    non-trading day or post-close
    MISS             no entry (never written, or TTL expired)

    11:45  LUNCH_BREAK, age 900s  → MARKET_PAUSED   (normal)
    10:45  CONTINUOUS_AM, age 900s → STALE           (data problem)

These are cache semantics — distinct from the Quality Gate verdicts
of Commit 006 (FRESH/WARNING/STALE/...), which judge the data; the
cache state judges what the *system* can rely on right now.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CacheState(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    MARKET_PAUSED = "MARKET_PAUSED"
    MARKET_CLOSED = "MARKET_CLOSED"
    MISS = "MISS"


class CacheBackendError(RuntimeError):
    """A cache backend operation failed (Redis unavailable, ...)."""


@dataclass(frozen=True)
class CacheConfig:
    """Market cache configuration — all env-driven, never hard-coded.

    Backend selection:
        REDIS_URL set   → Redis backend (shared across processes)
        REDIS_URL unset → in-memory backend (local dev / single
                          process — honest, clearly labelled)

    TTLs are session-aware (§6 + §7):
        ttl_trading_s — max lifetime while the market trades; bounds
                        how long a dead feed keeps serving STALE
                        quotes before the entry becomes a MISS
        ttl_closed_s  — max lifetime across closures (lunch,
                        overnight, weekend); quotes survive pauses
                        as MARKET_PAUSED, never forever
    """

    enabled: bool = True
    redis_url: Optional[str] = None
    ttl_trading_s: int = 3600
    ttl_closed_s: int = 86400

    @classmethod
    def from_env(cls) -> "CacheConfig":
        def _env_int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        enabled = os.environ.get(
            "MARKET_CACHE_ENABLED", "true"
        ).strip().lower() in ("1", "true", "yes", "on")
        url = os.environ.get("REDIS_URL") or None
        return cls(
            enabled=enabled,
            redis_url=url,
            ttl_trading_s=_env_int("MARKET_CACHE_TTL_TRADING_S", 3600),
            ttl_closed_s=_env_int("MARKET_CACHE_TTL_CLOSED_S", 86400),
        )

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "backend": "redis" if self.redis_url else "memory",
            "redis_url": self.redis_url,
            "ttl_trading_s": self.ttl_trading_s,
            "ttl_closed_s": self.ttl_closed_s,
        }


__all__ = ["CacheState", "CacheBackendError", "CacheConfig"]
