"""MarketDataService — the single standard read path for market data
(Commit 010).

Commits 001–009 built the market data infrastructure.  Commit 010 turns
it into a *platform service*: from here on, Dashboard, Paper Trading,
Strategy Runtime and any future consumer read market data through this
one object instead of reaching into the Adapter, Redis, the Quality Gate
or the Merge Engine themselves::

    Real Market Data
          ↓
    Adapter → Quote / 1m Bar → Session → Quality Gate → Redis Cache
          ↓
    Historical + Realtime Merge
          ↓
    MarketDataService            ← this module
       ┌──┴───────────────┐
       ▼                  ▼
    Paper Trading      Market Data API (HTTP)
    (in-process, §15)        ▼
                          Dashboard

§15 — Paper Trading calls this service **in-process**.  It never goes
out over HTTP to reach market data that lives in the same process.

Two rules this service enforces on every read:

1. **Nothing is fabricated.**  A symbol with no quote reports
   ``OFFLINE`` with ``last = None`` — never a guessed price.
2. **Quality is never bypassed** (§14).  A cached quote is always
   paired with its Quality Gate verdict, so a ``STALE`` quote can be
   served but can never masquerade as live data.

The service owns the lazy quote-feed lifecycle (previously inlined in
the Dashboard API module) so that ``/api/market-data`` and
``/api/dashboard`` provably share one ingestion pipeline.

Units & types: the wire format is JSON numbers for prices (the API
contract §12/§19), while the domain keeps ``Decimal``.  Conversion goes
through :func:`_num` — a parse failure yields ``None``, never 0.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .calendar.market_phase import PHASE_LABELS
from .calendar.trading_calendar import CST, calendar
from .domain.instrument import Exchange, InstrumentType

logger = logging.getLogger(__name__)

#: Timeframes the platform guarantees (Commit 004). Multi-timeframe
#: aggregation is explicitly out of scope until a later commit — an
#: unsupported value is a 400, never an empty list (§13).
SUPPORTED_TIMEFRAMES: tuple[str, ...] = ("1m",)

#: API bounds for ``limit`` (§13 — out-of-range is a parameter error).
MIN_BARS = 1
MAX_BARS = 500

#: How far back the per-symbol quarantine lookup scans the bounded ring.
_QUARANTINE_SCAN = 200

_UNSET = object()


# ══════════════════════════════════════════════════════════════════
# Errors — mapped to HTTP status codes by the API layer (§13)
# ══════════════════════════════════════════════════════════════════


class MarketDataServiceError(Exception):
    """Base class for market data service failures."""

    code = "MARKET_DATA_ERROR"
    status_code = 500

    def __init__(self, detail: str = "", **context: Any) -> None:
        super().__init__(detail or self.code)
        self.detail = detail or self.code
        self.context = context

    def as_dict(self) -> dict:
        payload: dict = {"error": self.code, "detail": self.detail}
        for key, value in self.context.items():
            # §13 types ``parameter`` / ``value`` as strings.  Coerce here
            # so an int-valued parameter (e.g. ``limit=0``) still renders
            # the documented envelope instead of a number.
            if key in ("parameter", "value") and value is not None:
                value = str(value)
            payload[key] = value
        return payload


class UnknownSymbolError(MarketDataServiceError):
    """Symbol is not registered in the Instrument Master → 404."""

    code = "MARKET_DATA_UNKNOWN_SYMBOL"
    status_code = 404


class InvalidParameterError(MarketDataServiceError):
    """Malformed request parameter → 400."""

    code = "MARKET_DATA_INVALID_PARAMETER"
    status_code = 400


class UnsupportedTimeframeError(InvalidParameterError):
    """Only 1m is supported → 400 (never an empty series, §13)."""

    code = "MARKET_DATA_UNSUPPORTED_TIMEFRAME"
    status_code = 400


class NoDataError(MarketDataServiceError):
    """Nothing to report yet for this resource → 404.

    Distinct from :class:`UnknownSymbolError`: the symbol exists, but
    no data has arrived, so no honest verdict can be produced.
    """

    code = "MARKET_DATA_NO_DATA"
    status_code = 404


class ServiceUnavailableError(MarketDataServiceError):
    """The market data pipeline cannot serve reads right now → 503."""

    code = "MARKET_DATA_UNAVAILABLE"
    status_code = 503


# ══════════════════════════════════════════════════════════════════
# Value coercion — Decimal/str → JSON number, never a fabricated 0
# ══════════════════════════════════════════════════════════════════


def _num(value: Any) -> Optional[float]:
    """Coerce a Decimal / str / number to float (None when absent)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _int(value: Any) -> Optional[int]:
    """Coerce to int (None when absent or unparseable)."""
    num = _num(value)
    return None if num is None else int(num)


def _bool(value: Any) -> bool:
    return bool(value)


class MarketDataService:
    """Read-path façade over the market data pipeline.

    Injected collaborators keep this testable and keep the singleton
    wiring in exactly one place (:func:`_build_default_service`).
    """

    def __init__(
        self,
        *,
        quote_service: object = None,
        bar_service: object = None,
        merge_engine: object = _UNSET,
        market_cache: object = _UNSET,
        trading_calendar: object = None,
        universe: object = None,
        feed_interval: float = 0.2,
        adapter_factory: object = None,
        clock: object = None,
    ) -> None:
        if quote_service is None:
            from .quote_service import quote_service as _qs

            quote_service = _qs
        if bar_service is None:
            from .aggregation.bar_service import bar_service as _bs

            bar_service = _bs
        if merge_engine is _UNSET:
            from .merge import merge_engine as _me

            merge_engine = _me
        if market_cache is _UNSET:
            from .cache import market_cache as _mc

            market_cache = _mc
        if universe is None:
            from .universe import universe as _uni

            universe = _uni

        self._quotes = quote_service
        self._bars_service = bar_service
        self._merge = merge_engine
        self._cache = market_cache
        self._cal = trading_calendar or calendar
        self._universe = universe
        self._interval = feed_interval
        self._adapter_factory = adapter_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

        # Lazy quote-feed lifecycle (moved out of the Dashboard API).
        self._feed: Optional[object] = None
        self._adapter: Optional[object] = None
        self._feed_lock = threading.Lock()
        self._unavailable: Optional[str] = None
        # Stateless gate used for read-path quality derivation (§14).
        self._derive_gate: Optional[object] = None

    # ── collaborators (§15 — Paper and API share these) ────────

    @property
    def quote_service(self) -> object:
        return self._quotes

    @property
    def bar_service(self) -> object:
        return self._bars_service

    @property
    def merge_engine(self) -> object:
        return self._merge

    @property
    def market_cache(self) -> object:
        return self._cache

    @property
    def trading_calendar(self) -> object:
        return self._cal

    @property
    def universe(self) -> object:
        return self._universe

    @property
    def timeframes(self) -> tuple[str, ...]:
        return SUPPORTED_TIMEFRAMES

    def paper_feed(self) -> object:
        """The Paper Trading feed, wired to this very service (§15).

        Paper Trading is an **in-process** consumer: it is handed the
        same quote service / bar service / merge engine / market cache
        this service reads from, so an order can never be priced from a
        different view of the market than the one the API reports.
        """
        from .paper import paper_market_feed

        return paper_market_feed

    def wiring(self) -> dict:
        """Diagnostic view of who is attached (§15)."""
        feed = self.paper_feed()
        return {
            "quote_service": type(self._quotes).__name__,
            "bar_service": type(self._bars_service).__name__,
            "merge_engine": type(self._merge).__name__,
            "market_cache": type(self._cache).__name__,
            "trading_calendar": type(self._cal).__name__,
            "paper_feed": type(feed).__name__,
            "paper_uses_service": (
                getattr(feed, "_quote_service", None) is self._quotes
            ),
        }

    # ── feed lifecycle ─────────────────────────────────────────

    @property
    def feed_started(self) -> bool:
        return self._feed is not None

    @property
    def feed_running(self) -> bool:
        return self._feed is not None and bool(
            getattr(self._feed, "running", False)
        )

    @property
    def adapter_name(self) -> str:
        if self._adapter is None:
            return "none"
        return str(getattr(self._adapter, "name", "unknown"))

    def ensure_feed(self) -> dict:
        """Start the quote feed on first use (idempotent).

        The single ingestion entry point: every API read that needs live
        data calls this, so a cold process can never serve a half-wired
        pipeline.  Raises :class:`ServiceUnavailableError` (503) when
        the ingestion thread cannot be started.
        """
        with self._feed_lock:
            if self.feed_running:
                return self._quotes.stats()
            # Adapter construction is part of "can the pipeline serve
            # reads?": a broken factory (e.g. a down broker socket) must
            # surface as 503, not escape as an unhandled 500.
            try:
                if self._adapter_factory is not None:
                    adapter = self._adapter_factory()
                else:
                    from .adapters.mock import MockMarketDataAdapter

                    adapter = MockMarketDataAdapter(seed=None)
                from .quote_service import QuoteFeed

                feed = QuoteFeed(
                    adapter,
                    self._quotes,
                    interval=self._interval,
                    bar_service=self._bars_service,
                    market_cache=self._cache,
                )
                feed.start(symbols=self._universe.symbols())
            except Exception as exc:  # noqa: BLE001 — surface as 503
                logger.exception("market data feed failed to start")
                self._unavailable = str(exc)
                raise ServiceUnavailableError(
                    f"market data feed could not be started: {exc}"
                ) from exc
            self._feed = feed
            self._adapter = adapter
            self._unavailable = None
            return self._quotes.stats()

    def restart_feed(self) -> dict:
        """(Re)start the feed — operator action, OPERATOR/ADMIN only."""
        self.stop_feed()
        return self.ensure_feed()

    def stop_feed(self) -> dict:
        with self._feed_lock:
            if self._feed is not None:
                try:
                    self._feed.stop()
                except Exception:  # noqa: BLE001 — stopping never raises
                    logger.exception("market data feed failed to stop")
                self._feed = None
            return {"running": False}

    # ── ① Instruments ──────────────────────────────────────────

    def instruments(
        self,
        *,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        instrument_type: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> dict:
        """The trading universe, optionally filtered (§2).

        Filters are validated: an unknown exchange / type / symbol is a
        parameter error, never a silently empty list.
        """
        rows = [self._instrument_row(i) for i in self._universe.all()]

        if symbol is not None:
            rows = self._filter_symbol(rows, symbol)
        if exchange is not None:
            wanted = self._validate_enum(
                exchange, Exchange, "exchange"
            )
            rows = [r for r in rows if r["exchange"] == wanted]
        if instrument_type is not None:
            wanted_t = self._validate_enum(
                instrument_type, InstrumentType, "instrument_type"
            )
            rows = [r for r in rows if r["instrument_type"] == wanted_t]
        if enabled is not None:
            rows = [r for r in rows if bool(r["enabled"]) is bool(enabled)]

        return {
            "items": rows,
            "count": len(rows),
            "total": self._universe.count,
            "filters": {
                "symbol": symbol,
                "exchange": exchange,
                "instrument_type": instrument_type,
                "enabled": enabled,
            },
            "exchanges": sorted({r["exchange"] for r in rows}),
            "instrument_types": sorted(
                {r["instrument_type"] for r in rows}
            ),
        }

    def instrument(self, symbol: str) -> dict:
        """One instrument or :class:`UnknownSymbolError` (404)."""
        return self._instrument_row(self._require_instrument(symbol))

    @staticmethod
    def _instrument_row(inst: object) -> dict:
        return {
            "symbol": inst.symbol,
            "name": inst.name,
            "exchange": inst.exchange.value,
            "instrument_type": inst.instrument_type.value,
            "currency": inst.currency,
            "lot_size": int(inst.lot_size),
            "tick_size": _num(inst.tick_size),
            "enabled": bool(inst.enabled),
            "trading_status": inst.trading_status.value,
        }

    def _filter_symbol(self, rows: list[dict], symbol: str) -> list[dict]:
        sym = str(symbol).strip()
        found = [r for r in rows if r["symbol"] == sym]
        if not found:
            raise UnknownSymbolError(
                f"Symbol {sym} is not in the trading universe",
                symbol=sym,
                value=sym,
            )
        return found

    @staticmethod
    def _validate_enum(value: str, enum_cls, field: str) -> str:
        """Validate a filter against an enum's values (400 on mismatch)."""
        raw = str(value).strip()
        allowed = [member.value for member in enum_cls]
        if raw not in allowed:
            raise InvalidParameterError(
                f"{field} must be one of {allowed}, got {raw!r}",
                parameter=field,
                value=raw,
                allowed=allowed,
            )
        return raw

    # ── ② / ③ / ④ Quotes ──────────────────────────────────────

    def quote(self, symbol: str) -> dict:
        """Latest quote + quality metadata for one symbol (§3).

        A registered symbol with no data yet is reported honestly as
        ``status="OFFLINE"`` / ``quality=null`` / ``last=null`` rather
        than being dressed up as a price.
        """
        inst = self._require_instrument(symbol)
        view = self._quote_view(inst)
        return view

    def quotes(
        self, symbols: Optional[list[str]] = None
    ) -> dict:
        """Batch quotes (§4).

        ``symbols=None`` → every enabled instrument.  Unknown symbols
        are a parameter error: silently dropping them would let a
        caller believe a symbol has no quote when in fact it was never
        requested correctly.
        """
        if symbols is None:
            wanted = [i.symbol for i in self._universe.enabled()]
        else:
            wanted = []
            for raw in symbols:
                sym = str(raw).strip()
                if not sym:
                    continue
                if not self._universe.contains(sym):
                    raise UnknownSymbolError(
                        f"Symbol {sym} is not in the trading universe",
                        symbol=sym,
                        value=sym,
                    )
                wanted.append(sym)
            # de-duplicate, keep request order
            wanted = list(dict.fromkeys(wanted))
        if not wanted:
            raise InvalidParameterError(
                "symbols must contain at least one symbol",
                parameter="symbols",
            )
        items = [self._quote_view(self._universe.get(s)) for s in wanted]
        return {
            "items": items,
            "count": len(items),
            "requested": len(wanted),
            "live_count": sum(1 for i in items if i["status"] == "LIVE"),
            "source": self.adapter_name,
        }

    def _quote_view(self, inst: object) -> dict:
        """Quote payload for one instrument (never fabricates a price)."""
        sym = inst.symbol
        quote = self._latest_quote(sym)
        base = {
            "symbol": sym,
            "name": inst.name,
            "exchange": inst.exchange.value,
            "instrument_type": inst.instrument_type.value,
            "currency": inst.currency,
            "lot_size": int(inst.lot_size),
            "tick_size": _num(inst.tick_size),
        }
        if quote is None:
            return {
                **base,
                "status": "OFFLINE",
                "quality": None,
                "tradable": False,
                "last": None,
                "bid": None,
                "ask": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "turnover": None,
                "open": None,
                "high": None,
                "low": None,
                "pre_close": None,
                "change": None,
                "change_pct": None,
                "spread": None,
                "timestamp": None,
                "received_timestamp": None,
                "quote_age_ms": None,
                "latency_ms": None,
            }
        age_s = quote.age_seconds()
        verdict = self._quality_verdict(sym)
        verdict_status = verdict.get("status")
        # Display status: LIVE only when the gate says FRESH.  Every
        # other verdict is surfaced verbatim (WARNING / STALE / ...)
        # so a caller can never mistake old data for live data (§14).
        status = (
            "LIVE"
            if verdict_status in (None, "FRESH")
            else str(verdict_status)
        )
        return {
            **base,
            "status": status,
            "quality": verdict.get("status"),
            "tradable": bool(verdict.get("tradable")),
            "last": _num(quote.last),
            "bid": _num(quote.bid),
            "ask": _num(quote.ask),
            "bid_size": _int(quote.bid_size),
            "ask_size": _int(quote.ask_size),
            "volume": _int(quote.volume),
            "turnover": _num(quote.turnover),
            "open": _num(quote.open),
            "high": _num(quote.high),
            "low": _num(quote.low),
            "pre_close": _num(quote.pre_close),
            "change": _num(quote.change),
            "change_pct": _num(quote.change_pct),
            "spread": _num(quote.spread),
            "timestamp": quote.timestamp.isoformat(),
            "received_timestamp": quote.effective_received_at.isoformat(),
            "quote_age_ms": int(age_s * 1000),
            "latency_ms": int(quote.latency_ms),
        }

    def _latest_quote(self, symbol: str) -> Optional[object]:
        try:
            return self._quotes.latest(symbol)
        except Exception:  # noqa: BLE001 — a broken source is a MISS
            logger.exception("quote source failed for %s", symbol)
            return None

    # ── ⑤ / ⑥ / ⑦ Bars ────────────────────────────────────────

    def bars(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict:
        """One unified 1m series: historical + realtime merged (§5/§6).

        The caller never receives two sources to stitch together, and
        the in-progress minute is always flagged ``is_closed=false``
        (§7) — the API never presents the current bar as finished.
        """
        inst = self._require_instrument(symbol)
        tf = str(timeframe or "1m").strip()
        if tf not in SUPPORTED_TIMEFRAMES:
            raise UnsupportedTimeframeError(
                f"timeframe {tf!r} is not supported; "
                f"supported: {list(SUPPORTED_TIMEFRAMES)}",
                parameter="timeframe",
                value=tf,
                # ``allowed`` is the §13 envelope field; ``supported`` is
                # kept as the human-facing alias the dashboard reads.
                allowed=list(SUPPORTED_TIMEFRAMES),
                supported=list(SUPPORTED_TIMEFRAMES),
            )
        if not isinstance(limit, int) or limit < MIN_BARS or limit > MAX_BARS:
            raise InvalidParameterError(
                f"limit must be between {MIN_BARS} and {MAX_BARS}",
                parameter="limit",
                value=limit,
            )
        start_dt = self._parse_datetime(start, "start")
        end_dt = self._parse_datetime(end, "end")
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise InvalidParameterError(
                "start must not be after end",
                parameter="start",
            )

        self.ensure_feed()

        # Cold start: anchor the history walk on the latest quote so the
        # chart lines up with the live price instead of floating.
        anchor = None
        latest = self._latest_quote(inst.symbol)
        if latest is not None:
            anchor = latest.last

        try:
            result = self._merge.unified(
                inst.symbol, tf, limit, anchor_price=anchor
            )
        except Exception as exc:  # noqa: BLE001 — merge failure → 503
            logger.exception("merge engine failed for %s", inst.symbol)
            raise ServiceUnavailableError(
                f"unified bar series unavailable: {exc}",
                symbol=inst.symbol,
            ) from exc

        from .quality.bar_quality import validate_bar

        items: list[dict] = []
        invalid: list[str] = []
        for bar, source in result["bars"]:
            if start_dt is not None and bar.timestamp < start_dt:
                continue
            if end_dt is not None and bar.timestamp > end_dt:
                continue
            if not validate_bar(bar).valid:
                invalid.append(bar.bar_id)
            items.append(self._bar_row(bar, source))

        counts = result["counts"]
        junction = result["junction"]
        revisions = [r.as_dict() for r in result["revisions"]]
        gaps = list(result["gaps"])
        return {
            "symbol": inst.symbol,
            "name": inst.name,
            "exchange": inst.exchange.value,
            "instrument_type": inst.instrument_type.value,
            "timeframe": tf,
            "items": items,
            "count": len(items),
            "closed_count": sum(1 for b in items if b["is_closed"]),
            "has_live": any(not b["is_closed"] for b in items),
            "start": start_dt.isoformat() if start_dt else None,
            "end": end_dt.isoformat() if end_dt else None,
            "gaps": gaps,
            "quality": {
                "checked": len(items),
                "invalid_count": len(invalid),
                "invalid_bars": invalid,
            },
            "merge": {
                "enabled": bool(self._merge.config.enabled),
                "historical_count": counts["historical"],
                "realtime_count": counts["realtime"],
                "overlaps": counts["overlaps"],
                "mode": junction["mode"],
                "seamless": junction["seamless"],
                "historical_last": junction["historical_last"],
                "realtime_first": junction["realtime_first"],
                "revision_count": len(revisions),
                "revisions": revisions,
                "gap_count": len(gaps),
            },
            "source": self.adapter_name,
        }

    @staticmethod
    def _bar_row(bar: object, source: str) -> dict:
        """One bar as the wire format (numbers, §5)."""
        return {
            "symbol": bar.symbol,
            "exchange": bar.exchange.value,
            "timeframe": bar.timeframe,
            "timestamp": bar.timestamp.isoformat(),
            "bar_id": bar.bar_id,
            "open": _num(bar.open),
            "high": _num(bar.high),
            "low": _num(bar.low),
            "close": _num(bar.close),
            "volume": _int(bar.volume),
            "turnover": _num(bar.turnover),
            "change": _num(bar.change),
            "change_pct": _num(bar.change_pct),
            "is_closed": bool(bar.is_closed),
            "source": source,
        }

    def _parse_datetime(
        self, value: Optional[str], field: str
    ) -> Optional[datetime]:
        """Parse an ISO-8601 filter; a naive value means exchange time."""
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidParameterError(
                f"{field} must be ISO-8601 (e.g. 2026-09-11T14:59:00+08:00), "
                f"got {raw!r}",
                parameter=field,
                value=raw,
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=CST)
        return parsed

    # ── ⑧ Session ─────────────────────────────────────────────

    def session(
        self,
        exchange: Optional[str] = None,
        *,
        at: Optional[datetime] = None,
    ) -> dict:
        """Current A-share market phase for one exchange (§8).

        Downstream code never re-implements "is the market open?" —
        ``is_tradable`` is the single gate.
        """
        wanted = (
            Exchange.SZSE
            if exchange is None
            else Exchange(self._validate_enum(exchange, Exchange, "exchange"))
        )
        now = at or self._clock()
        sess = self._cal.get_session(now, wanted)
        nphase, nat = self._cal.next_event(now)
        return {
            "exchange": sess.exchange.value,
            "market": sess.market,
            "trading_date": sess.trading_date.isoformat(),
            "phase": sess.phase.value,
            "phase_label": sess.phase_label,
            # Spec §8 shows clock times; the full instant is additive so
            # a consumer can still place the segment on a timeline.
            "session_start": (
                sess.session_start.strftime("%H:%M:%S")
                if sess.session_start
                else None
            ),
            "session_end": (
                sess.session_end.strftime("%H:%M:%S")
                if sess.session_end
                else None
            ),
            "session_start_at": (
                sess.session_start.isoformat() if sess.session_start else None
            ),
            "session_end_at": (
                sess.session_end.isoformat() if sess.session_end else None
            ),
            "is_trading_day": bool(sess.is_trading_day),
            "is_tradable": bool(sess.is_tradable),
            "next_event": {
                "phase": nphase.value,
                "label": PHASE_LABELS.get(nphase.value, nphase.value),
                "at": nat.isoformat(),
            },
            "server_time": now.isoformat(),
            "timezone": "Asia/Shanghai (UTC+8)",
        }

    def sessions(self, *, at: Optional[datetime] = None) -> dict:
        """Both exchanges in one call (Dashboard convenience)."""
        now = at or self._clock()
        return {
            "items": [
                self.session(e.value, at=now) for e in Exchange
            ],
            "server_time": now.isoformat(),
        }

    # ── ⑨ Quality ─────────────────────────────────────────────

    def quality(self, symbol: str) -> dict:
        """Latest Quality Gate verdict for one symbol (§9).

        Resolution order (most authoritative first):

        1. ``QuoteService.quality`` — the write-path gate's verdict, or
           a read-path derivation when no gate is attached
        2. the quarantine record (INVALID / QUARANTINED payloads are
           never stored as quotes, so this is the only place their
           verdict survives)
        3. the cached verdict

        Raises :class:`NoDataError` (404) when the symbol exists but
        nothing has been received yet — there is no verdict to report.
        """
        inst = self._require_instrument(symbol)
        verdict = self._quality_verdict(inst.symbol)
        if not verdict.get("status"):
            raise NoDataError(
                f"No quality verdict for {inst.symbol} yet "
                "(no data received)",
                symbol=inst.symbol,
            )
        checks = verdict.get("checks") or {}
        return {
            "symbol": inst.symbol,
            "name": inst.name,
            "status": verdict["status"],
            "tradable": bool(verdict.get("tradable")),
            "passed": bool(verdict.get("passed")),
            "action": verdict.get("action"),
            "checks": self._check_labels(checks),
            # No executed checks is not a pass: a quarantined payload
            # whose verdict came from the quarantine ring reports False
            # rather than claiming a clean bill of health.
            "checks_passed": bool(checks)
            and all(bool(v) for v in checks.values()),
            "reasons": list(verdict.get("reasons") or []),
            "quote_age_ms": _int(verdict.get("quote_age_ms")),
            "latency_ms": _int(verdict.get("latency_ms")),
            "checked_at": verdict.get("checked_at"),
            "source": verdict.get("source", "derived"),
            "config": self._quality_config().as_dict(),
        }

    @staticmethod
    def _check_labels(checks: dict) -> dict:
        """booleans → PASS/FAIL, the shape the API contract promises."""
        return {
            str(name): ("PASS" if bool(ok) else "FAIL")
            for name, ok in checks.items()
        }

    def quality_overview(self, *, limit: int = 0) -> dict:
        """Universe-wide quality roll-up + optional quarantine tail."""
        views = [self._quote_view(i) for i in self._universe.all()]
        counts = {
            "FRESH": 0,
            "WARNING": 0,
            "STALE": 0,
            "INVALID": 0,
            "QUARANTINED": 0,
            "OFFLINE": 0,
        }
        for v in views:
            key = v["quality"] or "OFFLINE"
            counts[key] = counts.get(key, 0) + 1
        items = []
        if limit > 0:
            items = self._quarantine_items(limit)
        return {
            "instruments": len(views),
            "counts": counts,
            "symbols": [
                {
                    "symbol": v["symbol"],
                    "name": v["name"],
                    "status": v["quality"] or "OFFLINE",
                    "tradable": v["tradable"],
                    "last": v["last"],
                    "quote_age_ms": v["quote_age_ms"],
                    "latency_ms": v["latency_ms"],
                }
                for v in views
            ],
            "quarantine_items": items,
            "config": self._quality_config().as_dict(),
        }

    def _quality_config(self):
        from .quality.quality_config import QualityConfig

        return QualityConfig.from_env()

    def _quality_gate(self) -> Optional[object]:
        try:
            return self._quotes.quality_gate
        except Exception:  # noqa: BLE001
            return None

    def _quality_verdict(self, symbol: str) -> dict:
        """Resolve the most authoritative verdict for a symbol (§14).

        Never returns a bare quote: every read is paired with a gate
        verdict, so a STALE quote cannot pass for live data.

        Resolution order, most authoritative first:

        1. ``QuoteService.quality`` — the write-path gate's verdict, or
           a read-path derivation when no gate is attached
        2. the quarantine record — INVALID / QUARANTINED payloads are
           dropped before storage, so this is where their verdict
           survives
        3. the cached verdict — survives a process restart
        4. a stateless read-path derivation from the latest quote, so a
           gate-less source still reports honest freshness instead of
           reading as LIVE
        """
        try:
            view = self._quotes.quality(symbol)
        except Exception:  # noqa: BLE001 — a broken gate must not 500
            logger.exception("quality lookup failed for %s", symbol)
            view = None
        if view and view.get("status"):
            return {**view, "source": "quote_service"}

        item = self._quarantined(symbol)
        if item is not None:
            return {
                "symbol": symbol,
                "status": item.get("status"),
                "passed": False,
                "tradable": False,
                "action": item.get("action"),
                "checks": {},
                "reasons": list(item.get("reasons") or []),
                "quote_age_ms": None,
                "latency_ms": None,
                "checked_at": item.get("received_at"),
                "source": "quarantine",
            }

        try:
            cached = self._cache.get_quality(symbol)
        except Exception:  # noqa: BLE001
            cached = None
        if cached and cached.get("status"):
            return {**cached, "source": "cache"}

        # 4. Read-path derivation — the stateless freshness / structural
        #    check the QuoteService runs when no write-path gate is
        #    attached.  Without this, a service wired to a gate-less
        #    quote source could not produce a verdict at all, and a
        #    stale quote would silently read as LIVE (§14).
        quote = self._latest_quote(symbol)
        if quote is not None:
            derived = self._derive_verdict(quote)
            if derived:
                return derived
        return {}

    def _derive_verdict(self, quote: object) -> dict:
        """Stateless verdict for a gate-less quote source (§14).

        Mirrors ``QuoteService``'s display fallback so every consumer
        sees the same quality semantics regardless of whether the
        write-path gate is enabled.  Never raises: a derivation failure
        degrades to "no verdict", never to a 500.
        """
        gate = self._display_gate()
        if gate is None:
            return {}
        try:
            result = gate.derive(quote, now=self._clock())
        except Exception:  # noqa: BLE001 — derivation must not 500
            logger.exception("quality derivation failed for %s", quote.symbol)
            return {}
        return {**result.as_dict(), "source": "derived"}

    def _display_gate(self):
        """Lazily-built stateless gate used for read-path derivation.

        Shares the service's trading calendar so a derivation can never
        disagree with ``/session`` about whether the market is open.
        """
        if self._derive_gate is None:
            try:
                from .quality.quality_gate import QualityGate

                self._derive_gate = QualityGate(trading_calendar=self._cal)
            except Exception:  # noqa: BLE001
                logger.exception("quality gate unavailable for derivation")
                return None
        return self._derive_gate

    def _quarantined(self, symbol: str) -> Optional[dict]:
        """Most recent quarantined payload for a symbol (or None).

        ``QuarantineStore.recent`` returns plain dicts (newest first),
        so the per-symbol lookup is a scan of the bounded ring.
        """
        gate = self._quality_gate()
        if gate is None:
            return None
        try:
            recent = gate.quarantine.recent(_QUARANTINE_SCAN)
        except Exception:  # noqa: BLE001
            return None
        for item in recent:
            if item.get("symbol") == symbol:
                return item
        return None

    def _quarantine_items(self, limit: int) -> list[dict]:
        """Trimmed quarantine tail for the overview endpoint."""
        gate = self._quality_gate()
        if gate is None:
            return []
        try:
            items = gate.quarantine.recent(limit)
        except Exception:  # noqa: BLE001
            return []
        return [
            {
                "symbol": item.get("symbol"),
                "status": item.get("status"),
                "reasons": list(item.get("reasons") or []),
                "action": item.get("action"),
                "received_at": item.get("received_at"),
            }
            for item in items
        ]

    # ── ⑩ Health ──────────────────────────────────────────────

    def health(self) -> dict:
        """System-level market data health (§10).

        Deliberately **non-mutating**: a health probe must be safe to
        call at any time, so it never starts the feed.  Use
        :attr:`feed_started` to tell "never started" apart from "down".
        """
        try:
            cache_health = self._cache.health()
        except Exception as exc:  # noqa: BLE001
            cache_health = {
                "status": "DEGRADED",
                "backend": "unknown",
                "enabled": False,
                "consecutive_failures": 0,
                "last_error": str(exc),
                "last_error_at": None,
                "trading_allowed": False,
            }

        views = [self._quote_view(i) for i in self._universe.all()]
        counts = {
            "total": len(views),
            "fresh": 0,
            "warning": 0,
            "stale": 0,
            "invalid": 0,
            "quarantined": 0,
            "offline": 0,
        }
        for v in views:
            status = v["quality"] or "OFFLINE"
            key = {
                "FRESH": "fresh",
                "WARNING": "warning",
                "STALE": "stale",
                "INVALID": "invalid",
                "QUARANTINED": "quarantined",
                "OFFLINE": "offline",
            }.get(status, "offline")
            counts[key] += 1

        adapter_up = self.feed_running
        redis_state = {
            "HEALTHY": "UP",
            "DISABLED": "DISABLED",
            "DEGRADED": "DEGRADED",
        }.get(cache_health.get("status"), "UNKNOWN")

        # ── overall verdict (§10 enum) ─────────────────────────
        if not adapter_up:
            status = "OFFLINE"
        elif counts["invalid"] or counts["quarantined"]:
            status = "BLOCKED"
        elif cache_health.get("status") == "DEGRADED":
            status = "BLOCKED"
        elif counts["offline"]:
            status = "OFFLINE"
        elif counts["stale"] or counts["warning"]:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        quality_state = (
            "HEALTHY"
            if status in ("HEALTHY",)
            else ("BLOCKED" if status == "BLOCKED" else "DEGRADED")
        )
        if status == "OFFLINE":
            quality_state = "OFFLINE"

        now = self._clock()
        session = self.session(at=now)
        return {
            "status": status,
            "adapter": "UP" if adapter_up else "DOWN",
            "redis": redis_state,
            "quality": quality_state,
            "symbols": counts,
            "instruments": len(views),
            "feed": {
                "started": self.feed_started,
                "running": self.feed_running,
                "adapter": self.adapter_name,
                "interval_seconds": self._interval,
                "stats": self._feed_stats(),
            },
            "cache": cache_health,
            "session": {
                "phase": session["phase"],
                "is_tradable": session["is_tradable"],
            },
            "timeframes": list(SUPPORTED_TIMEFRAMES),
            "server_time": now.isoformat(),
            "checked_at": now.isoformat(),
        }

    def _feed_stats(self) -> dict:
        try:
            return self._quotes.stats()
        except Exception:  # noqa: BLE001
            return {}

    # ── shared helpers ────────────────────────────────────────

    def _require_instrument(self, symbol: object):
        sym = str(symbol or "").strip()
        if not sym:
            raise InvalidParameterError(
                "symbol must not be empty", parameter="symbol"
            )
        inst = self._universe.get(sym)
        if inst is None:
            raise UnknownSymbolError(
                f"Symbol {sym} is not in the trading universe",
                symbol=sym,
                value=sym,
            )
        return inst


# ══════════════════════════════════════════════════════════════════
# Singleton — one pipeline, one service (§15)
# ══════════════════════════════════════════════════════════════════


def _build_default_service() -> MarketDataService:
    """Wire the singleton against the real pipeline collaborators."""
    return MarketDataService()


market_data_service: MarketDataService = _build_default_service()


__all__ = [
    "MarketDataService",
    "market_data_service",
    "MarketDataServiceError",
    "UnknownSymbolError",
    "InvalidParameterError",
    "UnsupportedTimeframeError",
    "NoDataError",
    "ServiceUnavailableError",
    "SUPPORTED_TIMEFRAMES",
    "MIN_BARS",
    "MAX_BARS",
]
