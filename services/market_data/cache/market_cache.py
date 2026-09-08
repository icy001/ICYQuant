"""MarketCache — the shared latest market state (Commit 007).

Position in the pipeline::

    Market Data Adapter → Normalizer → Trading Session (005)
                       → Quality Gate (006)   ← only passed data below
                       → MarketCache (007)
                       → API / Dashboard / Strategy / Paper

Redis is not a market data database.  The cache holds only the
latest, quality-passed Market State with session-aware TTLs so a
dead feed surfaces as MISS instead of serving zombie quotes
forever.

Core rules implemented here:

*   Atomic update (§9) — one quote = one single-key write of the
    complete serialized object.  Readers never observe a stitched
    state (last from B, timestamp from A, volume from C).

*   Timestamp protection (§10) — an inbound quote older than the
    cached one is refused (REJECT_STALE_UPDATE).  This is a
    different layer from Commit 006: the gate judges whether data
    is *problematic*; the cache protects itself from being
    overwritten by *older* data after reordering.  Phase 1 uses a
    GET-then-SET check (single-writer feed process); a
    multi-process writer would move the compare into a Lua script.

*   Session-aware TTL (§6 + §7) — see :class:`CacheConfig`.

*   Failure policy (§14 + §15) — a failing backend degrades the
    cache (DEGRADED) instead of pretending everything is fine; the
    trading path is then blocked while quote ingestion keeps
    retrying.  Cache write failures never propagate into the feed.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from ..calendar.market_phase import MarketPhase
from ..calendar.trading_calendar import TradingCalendar, calendar
from ..domain.instrument import Exchange
from ..quality.quality_config import QualityConfig
from .cache_models import (
    CacheBackendError,
    CacheConfig,
    CacheState,
)
from . import redis_keys as keys

logger = logging.getLogger(__name__)

# Phases where the market exists but continuous trading is paused.
_PAUSED_PHASES = (
    MarketPhase.PRE_OPEN,
    MarketPhase.AUCTION,
    MarketPhase.LUNCH_BREAK,
)


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class _MemoryBackend:
    """In-process backend (local dev / single process).

    Same contract as the Redis backend: string values, per-key TTL
    with lazy expiry, glob pattern inventory.  Honest about what it
    is — the health view labels the backend "memory".
    """

    name = "memory"

    def __init__(self, clock: Callable[[], datetime] = _default_clock):
        self._clock = clock
        self._lock = threading.Lock()
        self._data: dict[str, str] = {}
        self._expires: dict[str, datetime] = {}

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            exp = self._expires.get(key)
            if exp is not None and self._clock() >= exp:
                self._data.pop(key, None)
                self._expires.pop(key, None)
                return None
            return self._data.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = value
            self._expires[key] = self._clock() + timedelta(
                seconds=ttl_seconds
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._expires.pop(key, None)

    def keys(self, pattern: str) -> list[str]:
        import fnmatch

        with self._lock:
            return [
                k for k in self._data if fnmatch.fnmatch(k, pattern)
            ]

    def ping(self) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._expires.clear()


class _RedisBackend:
    """Redis backend — production shared cache.

    All operations raise :class:`CacheBackendError` on failure so the
    owning MarketCache can degrade honestly instead of faking
    success.  The client connects lazily (a configured-but-down
    Redis surfaces as DEGRADED on first use, §14).
    """

    name = "redis"

    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None

    def _connect(self):
        if self._client is None:
            import redis  # lazy: local dev machines may not have it

            self._client = redis.Redis.from_url(
                self._url, decode_responses=True
            )
        return self._client

    def get(self, key: str) -> Optional[str]:
        try:
            return self._connect().get(key)
        except Exception as exc:  # noqa: BLE001
            raise CacheBackendError(str(exc)) from exc

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self._connect().set(key, value, ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            raise CacheBackendError(str(exc)) from exc

    def delete(self, key: str) -> None:
        try:
            self._connect().delete(key)
        except Exception as exc:  # noqa: BLE001
            raise CacheBackendError(str(exc)) from exc

    def keys(self, pattern: str) -> list[str]:
        try:
            return list(self._connect().keys(pattern))
        except Exception as exc:  # noqa: BLE001
            raise CacheBackendError(str(exc)) from exc

    def ping(self) -> bool:
        try:
            return bool(self._connect().ping())
        except Exception as exc:  # noqa: BLE001
            raise CacheBackendError(str(exc)) from exc


class MarketCache:
    """Unified market state cache (§8).

    Business layers never touch the backend directly — they call::

        market_cache.set_quote(quote, quality=...)
        market_cache.get_quote(symbol)

    so the cache implementation (memory / Redis / whatever comes
    next) never leaks into business code.
    """

    @classmethod
    def from_env(cls) -> "MarketCache":
        """Config-driven construction (REDIS_URL selects the
        backend; unset → in-memory for local dev)."""
        return cls(config=CacheConfig.from_env())

    def __init__(
        self,
        *,
        config: Optional[CacheConfig] = None,
        backend: Optional[object] = None,
        trading_calendar: Optional[TradingCalendar] = None,
        quality_config: Optional[QualityConfig] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._cfg = config or CacheConfig.from_env()
        self._qcfg = quality_config or QualityConfig.from_env()
        self._cal = trading_calendar or calendar
        self._clock = clock or _default_clock
        if backend is None:
            backend = (
                _RedisBackend(self._cfg.redis_url)
                if self._cfg.redis_url
                else _MemoryBackend(clock=self._clock)
            )
        self._backend = backend
        self._lock = threading.Lock()
        # health (§14)
        self._consecutive_failures = 0
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None
        # stats
        self._writes = {"quote": 0, "bar": 0, "session": 0, "quality": 0}
        self._write_failures = 0
        self._stale_rejected = 0
        # session refresh bookkeeping (per exchange)
        self._session_sig: dict[str, tuple] = {}

    # ── properties ─────────────────────────────────────────────

    @property
    def config(self) -> CacheConfig:
        return self._cfg

    @property
    def enabled(self) -> bool:
        return self._cfg.enabled

    @property
    def degraded(self) -> bool:
        """§15: cache failure must never silently become bad trades."""
        return self._cfg.enabled and self._consecutive_failures > 0

    # ── write path (§8) ─────────────────────────────────────────

    def set_quote(
        self,
        quote,
        *,
        quality: Optional[dict] = None,
    ) -> bool:
        """Cache the latest quality-passed quote (atomic single-key
        replace, §9).

        ``quality`` — the Quality Gate verdict dict (Commit 006);
        its status is stored on the quote entry and the full verdict
        is cached under the quality key.

        Returns False when the update was refused (older timestamp,
        §10) or the backend failed (§14 — the feed keeps running).
        """
        if not self._cfg.enabled:
            return False
        key = keys.quote_key(quote.symbol)
        cached = self._read_json(key)
        if cached is not None:
            if _ts_ms(cached) > _quote_ts_ms(quote):
                self._stale_rejected += 1
                logger.debug(
                    "stale cache update rejected for %s "
                    "(cached %s > incoming %s)",
                    quote.symbol,
                    cached.get("timestamp"),
                    quote.timestamp.isoformat(),
                )
                return False
        now = self._clock()
        quality_status = (quality or {}).get("status")
        payload = dict(quote.as_dict())
        payload["quality_status"] = quality_status or "UNKNOWN"
        payload["cached_at"] = now.isoformat()
        payload["ts_ms"] = _quote_ts_ms(quote)
        payload["ttl_seconds"] = self._quote_ttl(now, quote.exchange)
        if self._write_json(key, payload, payload["ttl_seconds"]):
            self._writes["quote"] += 1
            self._refresh_session(quote.exchange, now)
            if quality is not None:
                verdict = dict(quality)
                verdict.setdefault("symbol", quote.symbol)
                self.set_quality(verdict)
            return True
        return False

    def set_bar(self, bar) -> bool:
        """Cache the latest bar (live or closed).  Same timestamp
        protection as quotes: an older bar never overwrites a newer
        one."""
        if not self._cfg.enabled:
            return False
        key = keys.bar_key(bar.timeframe, bar.symbol)
        cached = self._read_json(key)
        if cached is not None:
            if _ts_ms(cached) > _bar_ts_ms(bar):
                self._stale_rejected += 1
                return False
        now = self._clock()
        payload = dict(bar.as_dict())
        payload["cached_at"] = now.isoformat()
        payload["ts_ms"] = _bar_ts_ms(bar)
        payload["ttl_seconds"] = self._cfg.ttl_closed_s
        if self._write_json(key, payload, self._cfg.ttl_closed_s):
            self._writes["bar"] += 1
            return True
        return False

    def set_session(self, session) -> bool:
        """Cache the current trading session for an exchange."""
        if not self._cfg.enabled:
            return False
        data = session.as_dict() if hasattr(session, "as_dict") else session
        payload = dict(data)
        payload["cached_at"] = self._clock().isoformat()
        payload["ttl_seconds"] = self._cfg.ttl_closed_s
        key = keys.session_key(payload["exchange"])
        if self._write_json(key, payload, self._cfg.ttl_closed_s):
            self._writes["session"] += 1
            return True
        return False

    def set_quality(self, result) -> bool:
        """Cache the latest quality verdict for a symbol."""
        if not self._cfg.enabled:
            return False
        data = result.as_dict() if hasattr(result, "as_dict") else result
        payload = dict(data)
        payload["cached_at"] = self._clock().isoformat()
        payload["ttl_seconds"] = self._cfg.ttl_closed_s
        key = keys.quality_key(payload["symbol"])
        if self._write_json(key, payload, self._cfg.ttl_closed_s):
            self._writes["quality"] += 1
            return True
        return False

    # ── read path (§8 / §11) ────────────────────────────────────

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Latest cached quote payload (§5 shape) or None (MISS)."""
        if not self._cfg.enabled:
            return None
        return self._read_json(keys.quote_key(symbol))

    def get_latest_bar(self, symbol: str, timeframe: str = "1m") -> Optional[dict]:
        return self._read_json(keys.bar_key(timeframe, symbol)) if self._cfg.enabled else None

    def get_session(self, exchange: str) -> Optional[dict]:
        return self._read_json(keys.session_key(exchange)) if self._cfg.enabled else None

    def get_quality(self, symbol: str) -> Optional[dict]:
        return self._read_json(keys.quality_key(symbol)) if self._cfg.enabled else None

    def symbols(self) -> list[str]:
        """Symbols currently cached (quote keys inventory)."""
        try:
            found = self._backend.keys(keys.quote_pattern())
        except CacheBackendError:
            self._record_failure("keys")
            return []
        self._record_success()
        prefix = keys.quote_key("")
        return sorted(k[len(prefix):] for k in found)

    # ── cache state (§7) ───────────────────────────────────────

    def cache_state(
        self, symbol: str, *, now: Optional[datetime] = None
    ) -> CacheState:
        """Quote age + trading session combined into one honest
        verdict about what the system can rely on right now."""
        entry = self.get_quote(symbol)
        if entry is None:
            return CacheState.MISS
        now = now or self._clock()
        try:
            session = self._cal.get_session(now)
        except Exception:  # noqa: BLE001
            session = None
        if session is None or not session.is_trading_day:
            return CacheState.MARKET_CLOSED
        if session.phase in _PAUSED_PHASES:
            return CacheState.MARKET_PAUSED
        if session.phase is MarketPhase.POST_CLOSE:
            return CacheState.MARKET_CLOSED
        # continuous phase — freshness decides
        age = _age_seconds(entry, now)
        if age <= self._qcfg.fresh_ms / 1000:
            return CacheState.LIVE
        return CacheState.STALE

    def overview(self, symbols: Optional[list[str]] = None) -> dict:
        """§13 counts: cached / live / stale / paused / closed / miss."""
        symbols = symbols if symbols is not None else self.symbols()
        counts = {s.value: 0 for s in CacheState}
        for sym in symbols:
            counts[self.cache_state(sym).value] += 1
        return {
            "instruments": len(symbols),
            "counts": counts,
        }

    # ── health (§13 / §14 / §15) ───────────────────────────────

    def trading_allowed(self) -> bool:
        """§15 conservative policy: a degraded cache blocks the
        trading path (no new Paper / Shadow orders) while ingestion
        keeps retrying.  A disabled or healthy cache does not block
        — data quality itself remains the Quality Gate's job."""
        if not self._cfg.enabled:
            return True
        return self._consecutive_failures == 0

    def health(self) -> dict:
        backend_ok = True
        try:
            self._backend.ping()
        except CacheBackendError as exc:
            backend_ok = False
            self._record_failure(str(exc))
        else:
            self._record_success()
        if not self._cfg.enabled:
            status = "DISABLED"
        elif self._consecutive_failures > 0 or not backend_ok:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
        return {
            "status": status,
            "backend": self._backend.name,
            "enabled": self._cfg.enabled,
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._last_error,
            "last_error_at": (
                self._last_error_at.isoformat()
                if self._last_error_at
                else None
            ),
            "trading_allowed": self.trading_allowed(),
        }

    def stats(self) -> dict:
        with self._lock:
            return {
                "writes": dict(self._writes),
                "write_failures": self._write_failures,
                "stale_updates_rejected": self._stale_rejected,
            }

    def reset(self) -> None:
        with self._lock:
            self._writes = {"quote": 0, "bar": 0, "session": 0, "quality": 0}
            self._write_failures = 0
            self._stale_rejected = 0
            self._consecutive_failures = 0
            self._last_error = None
            self._last_error_at = None
            self._session_sig.clear()
        if hasattr(self._backend, "clear"):
            self._backend.clear()

    # ── internals ───────────────────────────────────────────────

    def _quote_ttl(self, now: datetime, exchange: Exchange) -> int:
        """Session-aware TTL (§6 + §7)."""
        try:
            session = self._cal.get_session(now, exchange)
            if session.is_tradable:
                return self._cfg.ttl_trading_s
        except Exception:  # noqa: BLE001
            pass
        return self._cfg.ttl_closed_s

    def _refresh_session(self, exchange: Exchange, now: datetime) -> None:
        """Refresh the session cache when the phase (or trading
        date) changes — cheap change detection, not per-tick SETs."""
        try:
            session = self._cal.get_session(now, exchange)
        except Exception:  # noqa: BLE001
            return
        sig = (session.trading_date.isoformat(), session.phase.value)
        prev = self._session_sig.get(exchange.value)
        if sig != prev:
            self.set_session(session)
            with self._lock:
                self._session_sig[exchange.value] = sig

    def _read_json(self, key: str) -> Optional[dict]:
        try:
            raw = self._backend.get(key)
        except CacheBackendError as exc:
            self._record_failure(str(exc))
            return None
        self._record_success()
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def _write_json(self, key: str, payload: dict, ttl_seconds: int) -> bool:
        try:
            self._backend.set(
                key, json.dumps(payload, ensure_ascii=False), ttl_seconds
            )
        except CacheBackendError as exc:
            self._record_failure(str(exc))
            logger.warning("market cache write failed (%s): %s", key, exc)
            return False
        self._record_success()
        return True

    def _record_failure(self, error: str) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._write_failures += 1
            self._last_error = error
            self._last_error_at = self._clock()

    def _record_success(self) -> None:
        with self._lock:
            if self._consecutive_failures:
                logger.info("market cache recovered")
            self._consecutive_failures = 0


def _quote_ts_ms(quote) -> int:
    return int(quote.timestamp.timestamp() * 1000)


def _bar_ts_ms(bar) -> int:
    return int(bar.timestamp.timestamp() * 1000)


def _ts_ms(entry: dict) -> int:
    return int(entry.get("ts_ms") or 0)


def _age_seconds(entry: dict, now: datetime) -> float:
    ts = entry.get("timestamp")
    if not ts:
        return float("inf")
    try:
        quoted = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return float("inf")
    return max(0.0, (now - quoted).total_seconds())


# ── Singleton used by the Dashboard API / QuoteFeed ─────────────
market_cache = MarketCache.from_env()

__all__ = ["MarketCache", "market_cache"]
