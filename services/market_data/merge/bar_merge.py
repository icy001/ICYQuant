"""Bar Merge Engine — historical + realtime → one unified 1m series.

Commit 008 turns "history ends at 10:34, realtime starts at 10:35"
into one continuous series::

    Historical Provider          BarService (realtime)
             └────────────┬────────────┘
                          ▼
                    BarMergeEngine
                          ▼
                  Unified 1m Series
                     ┌────┴────┐
                     ▼         ▼
                 Redis cache   API / Dashboard

Guarantees:

*   §5 ordering — output is strictly ``timestamp ASC``.
*   §6 identity  — merge key is symbol + exchange + timeframe +
    bar timestamp; one bucket appears exactly once.
*   §7 realtime-priority — for an unclosed bucket the realtime bar
    wins (fresher).
*   §8 closed-bar principle — when history and realtime disagree on
    a *closed* bucket the difference is recorded as a ``BarRevision``
    (audit trail), never silently overwritten; the realtime value is
    kept in the unified series as the system's live view.
*   §11 gap honesty — missing trading-phase minutes are reported as
    gaps, never fabricated; lunch breaks / closures are not gaps (§12).
*   §9/§10 cold & warm start — with no realtime the engine serves
    pure history (the cache is seeded with the newest merged bar via
    Commit 007's ``set_bar``, whose timestamp protection keeps older
    history from clobbering live state).
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from ..aggregation.bar_service import BarService
from ..cache import MarketCache
from ..calendar.trading_calendar import TradingCalendar, calendar
from ..domain.bar import Bar
from .historical_provider import SyntheticHistoricalProvider
from .merge_policy import BarRevision, MergePolicy, revision_now

logger = logging.getLogger(__name__)

HISTORICAL = "HISTORICAL"
REALTIME = "REALTIME"

# fields compared when checking a closed/closed bucket for revisions
_REVISION_FIELDS = (
    "open", "high", "low", "close", "volume", "turnover",
)


class BarMergeEngine:
    """Merges a historical provider with the realtime bar service."""

    def __init__(
        self,
        provider: object,
        *,
        bar_service: Optional[BarService] = None,
        policy: Optional[MergePolicy] = None,
        trading_calendar: Optional[TradingCalendar] = None,
        market_cache: Optional[MarketCache] = None,
    ) -> None:
        self._provider = provider
        self._realtime = bar_service
        self._cfg = policy or MergePolicy.from_env()
        self._cal = trading_calendar or calendar
        self._cache = market_cache
        self._lock = threading.Lock()
        self._revisions: dict[str, list[BarRevision]] = {}
        self._merges = 0

    # ── public API ─────────────────────────────────────────────

    @property
    def config(self) -> MergePolicy:
        return self._cfg

    def unified(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
        *,
        anchor_price: Optional[Decimal] = None,
    ) -> dict:
        """Unified series for one symbol, oldest first.

        Returns::

            {
              "bars":      [(Bar, source), ...]   # ASC, deduped
              "counts":    {"historical", "realtime",
                            "total", "overlaps"},
              "revisions": [BarRevision, ...]     # new this call
              "gaps":      ["202609081035", ...]  # §11, capped
              "junction":  {"historical_last", "realtime_first",
                            "mode", "seamless"},
            }
        """
        limit = max(1, min(limit, self._cfg.max_bars))
        realtime = self._realtime_bars(symbol, timeframe, limit)

        historical: list[Bar] = []
        if self._cfg.enabled:
            before = realtime[0].timestamp if realtime else None
            anchor: Optional[Decimal] = None
            if realtime:
                # seamlessness: history's newest close == realtime's
                # first open (§1 continuous chart)
                anchor = realtime[0].open
            elif anchor_price is not None:
                anchor = anchor_price
            # Budget the history walk so the *union* fits the limit.
            # Asking both sides for ``limit`` and only then tail-clipping
            # would return a series shorter than the inputs it reports,
            # breaking the merge-key identity (total = h + r - overlaps)
            # and silently dropping history the caller asked to see.
            try:
                historical = self._provider.bars(
                    symbol, timeframe, limit - len(realtime),
                    before=before, anchor_price=anchor,
                )
            except Exception:
                # history unavailable → degrade to realtime-only, the
                # series itself must never fail because history did
                logger.exception(
                    "historical provider failed for %s", symbol
                )
                historical = []
        # merge-key invariant (§6): only this symbol's 1m bars enter
        historical = [
            b for b in historical
            if b.symbol == symbol and b.timeframe == timeframe
        ]

        merged, revisions, overlaps = self._merge(
            symbol, timeframe, historical, realtime
        )
        if len(merged) > limit:
            merged = merged[-limit:]

        bars = [pair[0] for pair in merged]
        gaps = self._detect_gaps(symbol, bars)

        with self._lock:
            self._merges += 1
            if revisions:
                log = self._revisions.setdefault(symbol, [])
                log.extend(revisions)
                del log[:-self._cfg.revision_history]

        # §13 — merged latest state flows into the cache; set_bar's
        # timestamp protection keeps stale history from overwriting
        # live bars (cold start seeds, warm start no-ops)
        if self._cache is not None and bars:
            try:
                self._cache.set_bar(bars[-1])
            except Exception:
                logger.exception("cache write-through failed for %s", symbol)

        hist_ts = [b.timestamp for b in historical]
        rt_ts = [b.timestamp for b in realtime]
        mode = self._mode(len(hist_ts), len(rt_ts))
        return {
            "bars": merged,
            "counts": {
                "historical": len(hist_ts),
                "realtime": len(rt_ts),
                "total": len(bars),
                "overlaps": overlaps,
            },
            "revisions": revisions,
            "gaps": gaps,
            "junction": {
                "historical_last": (
                    hist_ts[-1].isoformat() if hist_ts else None
                ),
                "realtime_first": (
                    rt_ts[0].isoformat() if rt_ts else None
                ),
                "mode": mode,
                # seamless = joined with zero conflicting buckets
                "seamless": (
                    bool(hist_ts)
                    and bool(rt_ts)
                    and overlaps == 0
                ),
            },
        }

    def revisions(self, symbol: str) -> list[dict]:
        """Recorded bar revisions for a symbol (audit view, §8)."""
        with self._lock:
            return [r.as_dict() for r in self._revisions.get(symbol, [])]

    def stats(self) -> dict:
        with self._lock:
            return {
                "merges": self._merges,
                "revision_symbols": sorted(self._revisions),
                "revision_count": sum(
                    len(v) for v in self._revisions.values()
                ),
            }

    # ── internals ──────────────────────────────────────────────

    def _realtime_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> list[Bar]:
        if self._realtime is None or timeframe != "1m":
            return []
        try:
            return self._realtime.bars(symbol, limit)
        except Exception:
            logger.exception("realtime bars failed for %s", symbol)
            return []

    def _merge(
        self,
        symbol: str,
        timeframe: str,
        historical: list[Bar],
        realtime: list[Bar],
    ) -> tuple[list[tuple[Bar, str]], list[BarRevision], int]:
        """Dedup by bucket key, §7 realtime-priority, §8 revisions.

        Returns (merged pairs ASC, new revisions, overlap count).
        """
        table: dict = {}       # timestamp → (Bar, source)
        for bar in historical:
            table[bar.timestamp] = (bar, HISTORICAL)

        revisions: list[BarRevision] = []
        overlaps = 0
        for bar in realtime:
            existing = table.get(bar.timestamp)
            if existing is None:
                table[bar.timestamp] = (bar, REALTIME)
                continue
            overlaps += 1
            hist = existing[0]
            if hist.is_closed and bar.is_closed:
                # §8 — closed bucket changed: record, never silent
                revision = self._diff(symbol, timeframe, hist, bar)
                if revision is not None:
                    revisions.append(revision)
            # §7 — realtime is fresher and replaces either way
            table[bar.timestamp] = (bar, REALTIME)

        merged = [table[ts] for ts in sorted(table)]
        return merged, revisions, overlaps

    @staticmethod
    def _diff(
        symbol: str, timeframe: str, hist: Bar, rt: Bar
    ) -> Optional[BarRevision]:
        """Compare two closed bars of the same bucket."""
        fields = {}
        h = hist.as_dict()
        r = rt.as_dict()
        for name in _REVISION_FIELDS:
            if h.get(name) != r.get(name):
                fields[name] = (h.get(name), r.get(name))
        if not fields:
            return None
        return BarRevision(
            symbol=symbol,
            exchange=hist.exchange.value
            if hasattr(hist.exchange, "value") else str(hist.exchange),
            timeframe=timeframe,
            timestamp=hist.timestamp.isoformat(),
            fields=fields,
            detected_at=revision_now(),
        )

    def _detect_gaps(self, symbol: str, bars: list[Bar]) -> list[str]:
        """§11/§12 — missing trading-phase minutes between the first
        and last bar.  Closures and lunch breaks are not gaps; nothing
        is fabricated."""
        if len(bars) < 2:
            return []
        seen = {b.timestamp for b in bars}
        out: list[str] = []
        cursor = bars[0].timestamp
        last = bars[-1].timestamp
        guard = 0
        while cursor < last and guard < 100_000:
            guard += 1
            if (
                self._cal.is_bar_phase(cursor)
                and cursor not in seen
            ):
                # same id convention as the aggregator's gap ids
                out.append(f"{symbol}_{cursor.strftime('%Y%m%d%H%M')}")
                if len(out) >= self._cfg.gap_report_limit:
                    break
            cursor += timedelta(minutes=1)
        return out

    @staticmethod
    def _mode(hist_count: int, rt_count: int) -> str:
        if hist_count and rt_count:
            return "MERGED"
        if rt_count:
            return "REALTIME_ONLY"
        if hist_count:
            return "COLD"        # §9 — history only, feed not yet up
        return "EMPTY"


__all__ = ["BarMergeEngine", "HISTORICAL", "REALTIME"]
