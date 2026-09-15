"""Paper Market Feed — real market data for Paper Trading (Commit 009).

Commit 009 turns Paper Trading from a self-contained simulation into
the *first consumer of the real market data infrastructure*::

    Market Data Adapter            (001)
        ↓
    Instrument Master / Universe   (002)
        ↓
    Real-time Quote pipeline       (003)
        ↓
    1m Bar aggregation             (004)
        ↓
    Trading Session                (005)
        ↓
    Quality Gate                   (006)
        ↓
    Redis Market Cache             (007)
        ↓
    Historical + Realtime Merge    (008)
        ↓
    PaperMarketFeed                (009)
        ↓
    PaperTradingSession

Paper Trading therefore is::

    真实行情 + 真实交易时间 + 真实数据质量约束 + 模拟成交

and never ``Fake Price → Fake Order → Fake PnL``.

The feed **produces no market data of its own**.  It only decides
which already-quality-passed, already-merged real data Paper Trading
is allowed to act on:

*   §3  — the data path cannot bypass the Quality Gate: reads go
    through QuoteService / BarService / the merge engine, never
    straight to an adapter.
*   §5  — fill pricing prefers the book (BUY → ASK, SELL → BID) and
    records ``fill_price_source`` (ASK / BID / LAST) so Paper fill
    quality stays analysable.
*   §6  — one configurable ``slippage_bps`` hook (default 0).  Fixed /
    percentage / volatility / volume-impact models are out of scope.
*   §7  — no lookahead: a fill may only use data that had already
    arrived when the order was created, otherwise
    ``PAPER_LOOKAHEAD_VIOLATION``.
*   §8  — lot size comes from the Instrument Master, never a literal
    ``100``; a non-conforming quantity is ``PAPER_INVALID_LOT_SIZE``.
*   §10 — the Quality Gate is a hard gate (FRESH allows; WARNING is
    refused by default; STALE / INVALID / QUARANTINED never fill).
*   §11 — the Trading Session is a hard gate (lunch break / close /
    non-trading day produce no fills).
*   §12 — feed state READY / DEGRADED / BLOCKED / OFFLINE; a degraded
    cache blocks *new* orders rather than trading on blind guesses.
*   §17 — every block returns a machine-readable reason, never a bare
    ``False``.
*   §18 — the feed does not care *where* real data came from.  Commit
    012 §17 gives it two sources, ``LIVE`` and ``REPLAY``: one is
    today's pipeline, the other is history replayed on a virtual clock.
    Strategy is never told which one it is looking at.

Note on the quality accessor: :meth:`PaperMarketFeed.get_quality`
returns the same dict view QuoteService / the Dashboard expose
(``status`` / ``tradable`` / ``reasons`` / ``quote_age_ms``) instead
of the internal result dataclass, so Paper Trading and the UI can
never disagree about what "FRESH" meant at a given moment.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator, Optional

from ..calendar.session import TradingSession
from ..calendar.trading_calendar import TradingCalendar, calendar
from ..domain.bar import Bar
from ..domain.instrument import Exchange, Instrument
from ..domain.quote import MarketQuote
from ..universe import universe as default_universe
from .paper_feed_config import PaperFeedConfig
from .paper_feed_state import (
    FillPriceSource,
    PaperBlockedError,
    PaperFeedError,
    PaperFeedState,
    PaperFill,
    PaperOrderDecision,
)

logger = logging.getLogger(__name__)

# The one sentence the UI must never lose (§15).
DISCLAIMER = "PAPER — NO REAL MONEY"

# Commit 012 §17 — the two market-data sources Paper Trading can run on.
# A REPLAY feed is fed by ReplayMarketDataAdapter and clocked by the
# replay engine's virtual clock, so every session / lookahead / freshness
# decision is taken in *historical* time rather than today's.
LIVE_SOURCE = "LIVE"
REPLAY_SOURCE = "REPLAY"
_SOURCES = (LIVE_SOURCE, REPLAY_SOURCE)

_BPS = Decimal("10000")
_UNSET = object()

# Quality statuses that mean "this data must never fill an order".
_BLOCKING_QUALITY = {
    "WARNING": PaperFeedError.MARKET_DATA_WARNING,
    "STALE": PaperFeedError.MARKET_DATA_STALE,
    "INVALID": PaperFeedError.MARKET_DATA_INVALID,
    "QUARANTINED": PaperFeedError.MARKET_DATA_INVALID,
}


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class PaperMarketFeed:
    """Read-only bridge: real market pipeline → Paper Trading (§2)."""

    def __init__(
        self,
        *,
        config: Optional[PaperFeedConfig] = None,
        quote_service: object = None,
        bar_service: object = None,
        merge_engine: object = _UNSET,
        market_cache: object = _UNSET,
        trading_calendar: Optional[TradingCalendar] = None,
        instrument_master: object = None,
        clock: object = None,
        source: str = LIVE_SOURCE,
    ) -> None:
        self._cfg = config or PaperFeedConfig.from_env()
        self._source = str(source).upper()
        if self._source not in _SOURCES:
            raise ValueError(
                f"unsupported paper feed source {source!r}; "
                f"expected one of {list(_SOURCES)}"
            )
        if self._source == REPLAY_SOURCE and clock is None:
            # Commit 012 §26 — replay time and real time must never mix.
            # A REPLAY feed that silently fell back to ``datetime.now()``
            # would judge a 2026-09-10 order against today's session and
            # block (or allow) it for the wrong reason.
            raise ValueError(
                "source=REPLAY requires an explicit virtual clock so the "
                "session/lookahead gates run on replay time, not wall time"
            )
        self._cal = trading_calendar or calendar
        self._clock = clock or _default_clock
        self._instruments = instrument_master or default_universe

        if quote_service is None:
            from ..quote_service import quote_service as _qs

            quote_service = _qs
        if bar_service is None:
            from ..aggregation.bar_service import bar_service as _bs

            bar_service = _bs
        self._quote_service = quote_service
        self._bar_service = bar_service

        # §18 — the merged series is the normal source; an explicit
        # ``None`` disables it (used by tests / realtime-only setups).
        if merge_engine is _UNSET:
            self._merge = self._resolve_merge_engine()
        else:
            self._merge = merge_engine

        if market_cache is _UNSET:
            from ..cache import market_cache as _mc

            market_cache = _mc
        self._market_cache = market_cache

        # Re-entrant: helpers such as ``subscriptions()`` and
        # ``stats()`` legitimately nest (stats → state → subscriptions).
        self._lock = threading.RLock()
        self._subscriptions: list[str] = []
        self._stopped = threading.Event()
        self._display_gate = None
        # stats (§17 — every block leaves a trace)
        self._decisions: dict[str, int] = {}
        self._fills = 0

    # ── configuration / wiring ─────────────────────────────────

    @property
    def config(self) -> PaperFeedConfig:
        return self._cfg

    @property
    def source(self) -> str:
        """``LIVE`` or ``REPLAY`` (Commit 012 §17).

        Purely informational for the UI: the feed's behaviour is
        identical either way, which is the entire point.
        """
        return self._source

    @property
    def disclaimer(self) -> str:
        return DISCLAIMER

    @staticmethod
    def _resolve_merge_engine():
        try:
            from ..merge import merge_engine

            return merge_engine
        except Exception:  # noqa: BLE001 — degrade to realtime-only
            logger.exception("merge engine unavailable for paper feed")
            return None

    # ── subscription (§2 / §16) ────────────────────────────────

    def subscribe(self, symbols) -> list[str]:
        """Subscribe symbols to the feed.

        Accepts plain codes (``["159852"]``) or Instruments
        (``universe.enabled()``).  An unknown symbol is rejected
        outright — Paper Trading never trades what the Instrument
        Master does not know.
        """
        wanted = self._normalise(symbols)
        unknown = [s for s in wanted if self._instrument(s) is None]
        if unknown:
            raise PaperBlockedError(
                PaperFeedError.MARKET_DATA_UNAVAILABLE,
                symbol=",".join(unknown),
                detail="symbol not registered in the Instrument Master",
            )
        with self._lock:
            for sym in wanted:
                if sym not in self._subscriptions:
                    self._subscriptions.append(sym)
            return list(self._subscriptions)

    def unsubscribe(self, symbols) -> list[str]:
        drop = set(self._normalise(symbols))
        with self._lock:
            self._subscriptions = [
                s for s in self._subscriptions if s not in drop
            ]
            return list(self._subscriptions)

    def subscriptions(self) -> list[str]:
        with self._lock:
            return list(self._subscriptions)

    def subscribed(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._subscriptions

    # ── market data (§2 / §4) ──────────────────────────────────

    def get_quote(
        self, symbol: str, *, as_of: Optional[datetime] = None
    ) -> MarketQuote:
        """Latest real quote for a symbol.

        ``as_of`` — refuse data that arrived after this instant
        (§7 lookahead guard).  Raises :class:`PaperBlockedError`
        with ``PAPER_QUOTE_UNAVAILABLE`` when no quote exists.
        """
        quote = self._raw_quote(symbol)
        if quote is None:
            raise PaperBlockedError(
                PaperFeedError.QUOTE_UNAVAILABLE,
                symbol=symbol,
                detail="no quote has reached the pipeline yet",
            )
        if as_of is not None:
            detail = self._lookahead(quote, as_of)
            if detail is not None:
                raise PaperBlockedError(
                    PaperFeedError.LOOKAHEAD_VIOLATION,
                    symbol=symbol,
                    detail=detail,
                )
        return quote

    def latest_quote(
        self, symbol: str, *, as_of: Optional[datetime] = None
    ) -> Optional[MarketQuote]:
        """``get_quote`` without the exception (None = unavailable)."""
        try:
            return self.get_quote(symbol, as_of=as_of)
        except PaperBlockedError:
            return None

    def bars(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
        *,
        as_of: Optional[datetime] = None,
    ) -> list[Bar]:
        """Merged 1m series (Commit 008), oldest first.

        ``as_of`` drops bars whose bucket opens after the given
        instant — the feed never hands Paper Trading a bar from the
        future (§7).
        """
        out: list[Bar] = []
        if self._merge is not None:
            try:
                merged = self._merge.unified(symbol, timeframe, limit=limit)
                out = [bar for bar, _src in (merged.get("bars") or [])]
            except Exception:  # noqa: BLE001 — never break on merge errors
                logger.exception("merge engine failed for %s", symbol)
                out = []
        if not out and self._bar_service is not None and timeframe == "1m":
            try:
                out = list(self._bar_service.bars(symbol, limit))
            except Exception:  # noqa: BLE001
                logger.exception("bar service failed for %s", symbol)
                out = []
        if as_of is not None:
            out = [b for b in out if b.timestamp <= as_of]
        return out

    def get_bar(
        self,
        symbol: str,
        timeframe: str = "1m",
        *,
        as_of: Optional[datetime] = None,
    ) -> Optional[Bar]:
        """Latest bar for a symbol (None when nothing has closed yet)."""
        bars = self.bars(symbol, timeframe, limit=2, as_of=as_of)
        return bars[-1] if bars else None

    def get_quality(self, symbol: str) -> Optional[dict]:
        """Latest quality verdict view for a symbol (§10).

        Same dict shape QuoteService / the Dashboard use, so the gate
        cannot mean two different things in two places.
        """
        src = self._quote_service
        if src is not None and hasattr(src, "quality"):
            try:
                view = src.quality(symbol)
                if view is not None:
                    return view
            except Exception:  # noqa: BLE001 — fall back to derivation
                logger.exception("quality source failed for %s", symbol)
        quote = self._raw_quote(symbol)
        if quote is None:
            return None
        return self._display().derive(quote, now=self._clock()).as_dict()

    def get_session(
        self,
        exchange: Exchange = Exchange.SZSE,
        *,
        at: Optional[datetime] = None,
    ) -> TradingSession:
        """Trading session / phase for an exchange (Commit 005)."""
        return self._cal.get_session(at or self._clock(), exchange)

    def stream(
        self,
        symbols=None,
        *,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
        max_quotes: Optional[int] = None,
    ) -> Iterator[MarketQuote]:
        """Yield quotes for ``symbols`` as they change.

        The feed is a consumer, not a producer: this polls the quote
        pipeline and yields each *new* quote exactly once.  Stops on
        :meth:`stop`, ``timeout`` or ``max_quotes``.
        """
        subs = (
            self._normalise(symbols)
            if symbols is not None
            else self.subscriptions()
        )
        if not subs:
            return
        self.subscribe(subs)
        poll = (
            poll_interval
            if poll_interval is not None
            else self._cfg.poll_interval_s
        )
        deadline = (
            None if timeout is None else time.monotonic() + float(timeout)
        )
        seen: dict[str, str] = {}
        emitted = 0
        while not self._stopped.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                return
            for sym in subs:
                quote = self._raw_quote(sym)
                if quote is None:
                    continue
                key = quote.timestamp.isoformat()
                if seen.get(sym) == key:
                    continue
                seen[sym] = key
                emitted += 1
                yield quote
                if max_quotes is not None and emitted >= max_quotes:
                    return
            if deadline is not None and time.monotonic() >= deadline:
                return
            time.sleep(poll)

    def stop(self) -> None:
        """Stop any in-flight :meth:`stream`."""
        self._stopped.set()

    def reset(self) -> None:
        self._stopped.clear()
        with self._lock:
            self._subscriptions.clear()
            self._decisions.clear()
        self._fills = 0

    # ── fill pricing (§5 / §6) ─────────────────────────────────

    def fill_price(
        self,
        symbol: str,
        side: str,
        *,
        quote: Optional[MarketQuote] = None,
    ) -> tuple[Decimal, FillPriceSource]:
        """Reference price for a simulated fill, plus its provenance.

        BUY  → ASK (fallback LAST when the book is empty)
        SELL → BID (fallback LAST when the book is empty)
        """
        q = quote or self._raw_quote(symbol)
        if q is None:
            raise PaperBlockedError(
                PaperFeedError.QUOTE_UNAVAILABLE,
                symbol=symbol,
                detail="no quote to price the fill from",
            )
        side_u = str(side).upper()
        if side_u == "BUY":
            ref, source = (
                (q.ask, FillPriceSource.ASK)
                if q.ask > 0
                else (q.last, FillPriceSource.LAST)
            )
            price = ref * (1 + self._slippage())
        elif side_u == "SELL":
            ref, source = (
                (q.bid, FillPriceSource.BID)
                if q.bid > 0
                else (q.last, FillPriceSource.LAST)
            )
            price = ref * (1 - self._slippage())
        else:
            raise ValueError(f"unsupported paper side: {side!r}")
        if ref <= 0:
            raise PaperBlockedError(
                PaperFeedError.QUOTE_UNAVAILABLE,
                symbol=symbol,
                detail="quote carries no usable price",
            )
        return price, source

    # ── order gate (§7 / §8 / §10 / §11 / §12 / §17) ────────────

    def check_order(
        self,
        symbol: str,
        *,
        side: str = "BUY",
        quantity: Optional[int] = None,
        at: Optional[datetime] = None,
        order_timestamp: Optional[datetime] = None,
    ) -> PaperOrderDecision:
        """May this Paper order proceed against real market data?

        Always returns a verdict — a blocked result carries the §17
        reason code instead of raising, so the caller can render
        "why" without parsing exceptions.
        """
        now = at or self._clock()
        order_ts = order_timestamp or now
        session = self._session_or_none(now)
        phase = session.phase.value if session is not None else None

        def blocked(
            code: PaperFeedError,
            detail: str = "",
            *,
            quality: Optional[str] = None,
            age: Optional[int] = None,
        ) -> PaperOrderDecision:
            with self._lock:
                self._decisions[code.value] = (
                    self._decisions.get(code.value, 0) + 1
                )
            return PaperOrderDecision(
                allowed=False,
                reason=code.value,
                symbol=symbol,
                detail=detail,
                quote_age_ms=age,
                phase=phase,
                quality=quality,
            )

        if not self._cfg.enabled:
            return blocked(PaperFeedError.FEED_DEGRADED, "paper feed disabled")

        # §8 — quantity / instrument rules come from the Instrument
        # Master, never from a hard-coded lot.
        instrument = self._instrument(symbol)
        if instrument is None:
            return blocked(
                PaperFeedError.MARKET_DATA_UNAVAILABLE,
                "symbol is not registered in the Instrument Master",
            )
        if quantity is not None and self._cfg.enforce_lot_size:
            lot = int(getattr(instrument, "lot_size", 1) or 1)
            qty = int(quantity)
            if qty <= 0 or qty % lot != 0:
                return blocked(
                    PaperFeedError.INVALID_LOT_SIZE,
                    f"quantity {qty} is not a positive multiple of lot {lot}",
                )

        # §12 — a failing cache blocks new orders (never trade blind).
        if self._cfg.require_healthy_cache and self._cache_degraded():
            return blocked(
                PaperFeedError.FEED_DEGRADED,
                "market cache is DEGRADED — new orders are blocked",
            )

        # §11 — session gate.  Checked before quality on purpose: a
        # closed market is not a data-quality problem, and the reason
        # code should say so.
        if self._cfg.enforce_session and (
            session is None or not session.is_tradable
        ):
            return blocked(
                PaperFeedError.SESSION_BLOCKED,
                f"phase {phase} does not allow continuous trading",
            )

        quote = self._raw_quote(symbol)
        if quote is None:
            return blocked(
                PaperFeedError.QUOTE_UNAVAILABLE, "no quote received"
            )
        age_ms = int(quote.age_seconds(now) * 1000)

        # Impossible data: a timestamp we have not reached yet.
        horizon = now + timedelta(
            milliseconds=self._cfg.lookahead_tolerance_ms
        )
        if quote.timestamp > horizon:
            return blocked(
                PaperFeedError.MARKET_DATA_INVALID,
                f"quote timestamp {quote.timestamp.isoformat()} is in the future",
                age=age_ms,
            )

        # §7 — the fill may only use data already in the system when
        # the order was created.
        detail = self._lookahead(quote, order_ts)
        if detail is not None:
            return blocked(
                PaperFeedError.LOOKAHEAD_VIOLATION, detail, age=age_ms
            )

        # §10 — quality gate as a hard gate.
        quality = self.get_quality(symbol)
        qstatus = (quality or {}).get("status")
        code = self._quality_block(quality)
        if code is not None:
            if self._cfg.enforce_quality or code in (
                PaperFeedError.MARKET_DATA_INVALID,
                PaperFeedError.QUOTE_UNAVAILABLE,
            ):
                return blocked(
                    code,
                    f"quality gate reports {qstatus}",
                    quality=qstatus,
                    age=age_ms,
                )

        # §5 — price the fill from the book.
        try:
            price, source = self.fill_price(symbol, side, quote=quote)
        except PaperBlockedError as exc:
            return blocked(exc.code, exc.detail, quality=qstatus, age=age_ms)

        return PaperOrderDecision(
            allowed=True,
            symbol=symbol,
            detail="ok",
            quote_age_ms=age_ms,
            phase=phase,
            quality=qstatus,
            fill_price=price,
            fill_price_source=source.value,
        )

    def can_trade(self, symbol: str, **kwargs) -> bool:
        """Boolean convenience over :meth:`check_order`."""
        return self.check_order(symbol, **kwargs).allowed

    def preview_fill(
        self,
        symbol: str,
        side: str,
        quantity: int,
        *,
        at: Optional[datetime] = None,
        order_timestamp: Optional[datetime] = None,
    ) -> PaperOrderDecision:
        """Validate + price an order without submitting it.

        ``allowed=True`` decisions carry ``fill_price`` /
        ``fill_price_source``; blocked ones carry the §17 reason.
        """
        return self.check_order(
            symbol,
            side=side,
            quantity=quantity,
            at=at,
            order_timestamp=order_timestamp,
        )

    def fill(
        self,
        symbol: str,
        side: str,
        quantity: int,
        *,
        at: Optional[datetime] = None,
        order_timestamp: Optional[datetime] = None,
    ) -> PaperFill:
        """Simulate a fill from the current real quote (§9).

        Raises :class:`PaperBlockedError` when the order gate refuses
        — Paper Trading must never invent a price to keep going.
        """
        decision = self.preview_fill(
            symbol,
            side,
            quantity,
            at=at,
            order_timestamp=order_timestamp,
        )
        if not decision.allowed:
            raise PaperBlockedError(
                PaperFeedError(decision.reason),
                symbol=symbol,
                detail=decision.detail,
            )
        quote = self._raw_quote(symbol)
        now = at or self._clock()
        with self._lock:
            self._fills += 1
        return PaperFill(
            symbol=symbol,
            side=str(side).upper(),
            quantity=int(quantity),
            price=decision.fill_price,
            price_source=decision.fill_price_source,
            slippage_bps=self._cfg.slippage_bps,
            quote_timestamp=quote.timestamp,
            fill_timestamp=now,
            order_timestamp=order_timestamp or now,
            quality=decision.quality,
            phase=decision.phase,
        )

    # ── state / health (§12 / §14) ─────────────────────────────

    @property
    def state(self) -> PaperFeedState:
        if not self._cfg.enabled:
            return PaperFeedState.OFFLINE
        subs = self.subscriptions()
        if not subs:
            return PaperFeedState.OFFLINE
        if not any(self._raw_quote(s) is not None for s in subs):
            return PaperFeedState.OFFLINE
        if self._cfg.require_healthy_cache and self._cache_degraded():
            return PaperFeedState.DEGRADED
        if self._cfg.enforce_session:
            session = self._session_or_none(self._clock())
            if session is None or not session.is_tradable:
                return PaperFeedState.BLOCKED
        # §12 — READY means market OPEN *and* quality FRESH *and* cache
        # HEALTHY.  A symbol whose data the gate refuses is not READY.
        if self._cfg.enforce_quality:
            for sym in subs:
                if self._quality_block(self.get_quality(sym)) is not None:
                    return PaperFeedState.BLOCKED
        return PaperFeedState.READY

    @property
    def ready(self) -> bool:
        return self.state is PaperFeedState.READY

    def symbol_status(
        self, symbol: str, *, now: Optional[datetime] = None
    ) -> dict:
        """One row of the Paper feed view (§14) for a symbol."""
        now = now or self._clock()
        instrument = self._instrument(symbol)
        quote = self._raw_quote(symbol)
        quality = self.get_quality(symbol)
        decision = self.check_order(symbol, at=now, order_timestamp=now)
        return {
            "symbol": symbol,
            "name": getattr(instrument, "name", "") if instrument else "",
            "lot_size": getattr(instrument, "lot_size", None),
            "tradable": decision.allowed,
            "blocked_reason": decision.reason,
            "quality": (quality or {}).get("status"),
            "phase": decision.phase,
            "quote_age_ms": decision.quote_age_ms,
            "last": str(quote.last) if quote is not None else None,
            "bid": str(quote.bid) if quote is not None else None,
            "ask": str(quote.ask) if quote is not None else None,
            "fill_price": (
                str(decision.fill_price)
                if decision.fill_price is not None
                else None
            ),
            "fill_price_source": decision.fill_price_source,
        }

    def status(self, symbols=None) -> dict:
        """Paper feed status payload for the Dashboard (§12 / §14)."""
        now = self._clock()
        syms = (
            self._normalise(symbols)
            if symbols is not None
            else self.subscriptions()
        )
        rows = [self.symbol_status(s, now=now) for s in syms]
        try:
            market = self._cal.status(now)
        except Exception:  # noqa: BLE001
            market = {}
        return {
            "environment": "PAPER",
            "disclaimer": DISCLAIMER,
            "source": self._source,
            "state": self.state.value,
            "ready": self.ready,
            "new_orders_allowed": self.state
            in (PaperFeedState.READY, PaperFeedState.BLOCKED),
            "backend": self._cache_health().get("backend")
            if self._cache_health()
            else None,
            "market": market,
            "cache": self._cache_health(),
            "config": self._cfg.as_dict(),
            "instruments": len(syms),
            "tradable": sum(1 for r in rows if r["tradable"]),
            "blocked": sum(1 for r in rows if not r["tradable"]),
            "rows": rows,
        }

    def stats(self) -> dict:
        # resolve the state first: it fans out into quotes / cache /
        # session and must not run while the subscription lock is held
        state = self.state.value
        with self._lock:
            return {
                "subscriptions": len(self._subscriptions),
                "fills_simulated": self._fills,
                "blocked_by_reason": dict(self._decisions),
                "state": state,
            }

    # ── internals ──────────────────────────────────────────────

    def _slippage(self) -> Decimal:
        return Decimal(str(self._cfg.slippage_bps)) / _BPS

    def _instrument(self, symbol: str) -> Optional[Instrument]:
        if self._instruments is None:
            return None
        try:
            return self._instruments.get(symbol)
        except Exception:  # noqa: BLE001
            return None

    def _raw_quote(self, symbol: str) -> Optional[MarketQuote]:
        src = self._quote_service
        if src is None:
            return None
        try:
            return src.latest(symbol)
        except Exception:  # noqa: BLE001 — a broken source is a MISS
            logger.exception("quote source failed for %s", symbol)
            return None

    def _session_or_none(self, at: datetime) -> Optional[TradingSession]:
        try:
            return self._cal.get_session(at)
        except Exception:  # noqa: BLE001
            logger.exception("trading calendar failed")
            return None

    def _display(self):
        """Stateless quality gate used when no write-path gate exists."""
        if self._display_gate is None:
            from ..quality.quality_gate import QualityGate

            self._display_gate = QualityGate()
        return self._display_gate

    def _quality_block(
        self, quality: Optional[dict]
    ) -> Optional[PaperFeedError]:
        """Map a quality verdict onto the §10 hard gate."""
        if quality is None:
            return PaperFeedError.QUOTE_UNAVAILABLE
        status = quality.get("status")
        if status in (None, "OFFLINE"):
            return PaperFeedError.QUOTE_UNAVAILABLE
        if status == "WARNING" and self._cfg.allow_warning_trading:
            return None
        tradable = quality.get("tradable")
        if tradable is None:
            tradable = status == "FRESH"
        if tradable:
            return None
        return _BLOCKING_QUALITY.get(
            status, PaperFeedError.MARKET_DATA_INVALID
        )

    def _lookahead(
        self, quote: MarketQuote, order_timestamp: datetime
    ) -> Optional[str]:
        """§7 — did this data exist when the order was created?"""
        limit = order_timestamp + timedelta(
            milliseconds=self._cfg.lookahead_tolerance_ms
        )
        if quote.effective_received_at > limit:
            return (
                "quote arrived at "
                f"{quote.effective_received_at.isoformat()} but the order "
                f"was created at {order_timestamp.isoformat()}"
            )
        if quote.timestamp > limit:
            return (
                f"quote timestamp {quote.timestamp.isoformat()} is after "
                f"the order at {order_timestamp.isoformat()}"
            )
        return None

    def _cache_degraded(self) -> bool:
        cache = self._market_cache
        if cache is None:
            return False
        try:
            if getattr(cache, "degraded", False):
                return True
            return cache.trading_allowed() is False
        except Exception:  # noqa: BLE001 — an unknown cache is not trusted
            logger.exception("market cache health check failed")
            return True

    def _cache_health(self) -> Optional[dict]:
        cache = self._market_cache
        if cache is None:
            return None
        try:
            return cache.health()
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _normalise(symbols) -> list[str]:
        """Accept codes or Instruments, dedupe, keep order (§16)."""
        if symbols is None:
            return []
        if isinstance(symbols, (str, Instrument)):
            symbols = [symbols]
        out: list[str] = []
        for item in symbols:
            code = getattr(item, "symbol", item)
            code = str(code).strip()
            if code and code not in out:
                out.append(code)
        return out


# ── Singleton used by the Dashboard API / Paper runtime ─────────
paper_market_feed = PaperMarketFeed()

__all__ = [
    "PaperMarketFeed",
    "paper_market_feed",
    "DISCLAIMER",
    "LIVE_SOURCE",
    "REPLAY_SOURCE",
]
