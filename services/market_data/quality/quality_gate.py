"""Market Data Quality Gate (Commit 006).

The first safety gate of the market data layer.  Architecture::

    Real-time Quote
          ↓
    Quote Normalizer (adapter)
          ↓
    Trading Session (Commit 005)
          ↓
    ┌──────────────────────┐
    │   Quality Gate       │
    └──────────┬───────────┘
         ┌────┴─────┐
       PASS       REJECT
         ↓           ↓
    Strategy      Quarantine
    Paper

Checks executed per quote (stateless ones can also be derived
on read for display):

    symbol / exchange     structural identity
    timestamp             tz-aware, not in the future (± tolerance)
    duplicate             symbol + exchange_timestamp + sequence_id
    regression            exchange timestamp went backwards
    cross_day_jump        skipped an entire trading day
    price                 last / bid / ask non-negative
    bid_ask               bid <= ask (no crossed book)
    outlier               price deviation vs previous quote —
                         MARKED, never modified (limit-up,
                         resumption, ex-rights are real moves)
    volume                volume / turnover non-negative, cumulative
                         volume monotonic within a trading day
    session               tradable phase right now (Commit 005)

Status aggregation (worst wins):

    any structural failure      → INVALID
    price outlier               → QUARANTINED
    stale freshness             → STALE
    warning freshness / market
    closed (session inactive)   → WARNING
    otherwise                   → FRESH
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from ..calendar.trading_calendar import TradingCalendar, calendar
from ..domain.instrument import Exchange
from ..domain.quote import MarketQuote
from .quality_config import QualityConfig
from .quality_result import MarketDataQualityResult
from .quality_status import QualityStatus
from .quarantine import QuarantineStore


def _freshness_status(
    age_ms: int, cfg: QualityConfig
) -> QualityStatus:
    if age_ms <= cfg.fresh_ms:
        return QualityStatus.FRESH
    if age_ms < cfg.stale_line_ms:
        return QualityStatus.WARNING
    return QualityStatus.STALE


class QualityGate:
    """Stateful per-symbol quality engine.

    ``evaluate`` runs on the write path (every inbound quote);
    ``derive`` runs the stateless subset on the read path (for
    display when no full evaluation has happened).
    """

    def __init__(
        self,
        *,
        config: Optional[QualityConfig] = None,
        trading_calendar: Optional[TradingCalendar] = None,
        quarantine: Optional[QuarantineStore] = None,
    ) -> None:
        self._cfg = config or QualityConfig.from_env()
        self._cal = trading_calendar or calendar
        self._quarantine = quarantine or QuarantineStore()
        self._lock = threading.Lock()
        # duplicate identity LRU: identity → None
        self._seen: OrderedDict[tuple, None] = OrderedDict()
        # per-symbol baselines (updated only by clean quotes)
        self._last_ts: dict[str, datetime] = {}
        self._last_volume: dict[str, int] = {}
        self._last_volume_day: dict[str, date] = {}
        self._last_price: dict[str, Decimal] = {}
        # per-symbol last full verdict (for API display)
        self._last_result: dict[str, MarketDataQualityResult] = {}
        # stats
        self._evaluated = 0
        self._rejected = 0
        self._by_status: dict[str, int] = {}

    # ── properties ─────────────────────────────────────────────

    @property
    def config(self) -> QualityConfig:
        return self._cfg

    @property
    def quarantine(self) -> QuarantineStore:
        return self._quarantine

    # ── write path ─────────────────────────────────────────────

    def evaluate(
        self,
        quote: MarketQuote,
        *,
        sequence_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> MarketDataQualityResult:
        """Full quality evaluation of an inbound quote.

        Thread-safe: called from the QuoteFeed thread while the API
        reads ``last_result`` / ``stats`` concurrently.
        """
        now = now or datetime.now(timezone.utc)
        checks: dict[str, bool] = {}
        reasons: list[str] = []
        cfg = self._cfg

        # ── identity ────────────────────────────────────────────
        ok_symbol = (
            isinstance(quote.symbol, str)
            and quote.symbol.isdigit()
            and len(quote.symbol) == 6
        )
        checks["symbol"] = ok_symbol
        if not ok_symbol:
            reasons.append("INVALID_SYMBOL")

        ok_exchange = isinstance(quote.exchange, Exchange)
        checks["exchange"] = ok_exchange
        if not ok_exchange:
            reasons.append("INVALID_EXCHANGE")

        # ── timestamp ────────────────────────────────────────────
        ts_ok = quote.timestamp.tzinfo is not None
        future = False
        if ts_ok:
            future = quote.timestamp > (
                now + timedelta(milliseconds=cfg.future_tolerance_ms)
            )
        checks["timestamp"] = ts_ok and not future
        if not ts_ok:
            reasons.append("TIMESTAMP_NOT_AWARE")
        elif future:
            reasons.append("FUTURE_TIMESTAMP")

        # ── freshness (age vs thresholds) ────────────────────────
        age_ms = int(quote.age_seconds(now) * 1000)
        freshness = _freshness_status(age_ms, cfg)
        checks["freshness"] = freshness is not QualityStatus.STALE

        # ── price ────────────────────────────────────────────────
        ok_price = (
            isinstance(quote.last, Decimal)
            and isinstance(quote.bid, Decimal)
            and isinstance(quote.ask, Decimal)
            and quote.last >= 0
            and quote.bid >= 0
            and quote.ask >= 0
        )
        checks["price"] = ok_price
        if not ok_price:
            reasons.append("INVALID_PRICE")

        ok_ba = ok_price and quote.bid <= quote.ask
        checks["bid_ask"] = ok_ba
        if ok_price and not ok_ba:
            reasons.append("CROSSED_BOOK")

        # ── volume / turnover ────────────────────────────────────
        ok_volume = quote.volume >= 0 and quote.turnover >= 0
        checks["volume"] = ok_volume
        if not ok_volume:
            reasons.append("INVALID_VOLUME")

        # ── session (Commit 005 connection) ─────────────────────
        session_active = False
        try:
            session_active = self._cal.is_tradable(quote.timestamp)
        except Exception:
            session_active = False
        checks["session"] = session_active
        if not session_active:
            reasons.append("SESSION_INACTIVE")

        # ── stateful checks (locked snapshot of baselines) ──────
        with self._lock:
            prev_ts = self._last_ts.get(quote.symbol)
            prev_price = self._last_price.get(quote.symbol)
            prev_volume = self._last_volume.get(quote.symbol)
            prev_volume_day = self._last_volume_day.get(quote.symbol)

        # duplicate: symbol + exchange_timestamp + sequence_id
        identity = (
            quote.symbol,
            quote.timestamp.isoformat() if ts_ok else "",
            sequence_id or "",
        )
        duplicate = identity in self._seen
        checks["duplicate"] = not duplicate
        if duplicate:
            reasons.append("DUPLICATE")

        # timestamp regression: older tick after a newer one
        regressed = ts_ok and prev_ts is not None and quote.timestamp < prev_ts
        # cross-day jump: forward jump skipping a whole trading day
        cross_day = False
        if ts_ok and prev_ts is not None and quote.timestamp > prev_ts:
            try:
                prev_day = self._cal.trading_date_of(prev_ts)
                quote_day = self._cal.trading_date_of(quote.timestamp)
                if (
                    quote_day != prev_day
                    and quote_day != self._cal.next_trading_day(prev_day)
                ):
                    cross_day = True
            except Exception:
                cross_day = False
        checks["regression"] = not regressed and not cross_day
        if regressed:
            reasons.append("TIMESTAMP_REGRESSION")
        elif cross_day:
            reasons.append("CROSS_DAY_JUMP")

        # price outlier: deviation vs previous clean price —
        # marked, never modified (real limit moves survive as
        # QUARANTINED so a human / later logic can confirm).
        outlier = False
        deviation_pct = Decimal("0")
        if ok_price and prev_price is not None and prev_price > 0:
            deviation_pct = abs(quote.last - prev_price) / prev_price * 100
            if deviation_pct > cfg.outlier_pct:
                outlier = True
        checks["outlier"] = not outlier
        if outlier:
            reasons.append("PRICE_OUTLIER")

        # cumulative volume regression within the same trading day;
        # a drop across trading days is a normal session reset
        volume_reg = False
        if ok_volume and prev_volume is not None:
            quote_day = self._cal.trading_date_of(quote.timestamp)
            if quote.volume < prev_volume and quote_day == prev_volume_day:
                volume_reg = True
        if volume_reg:
            checks["volume"] = False
            reasons.append("VOLUME_REGRESSION")

        # ── status aggregation (worst wins) ──────────────────────
        structural_fail = any(
            (
                not ok_symbol,
                not ok_exchange,
                not ts_ok,
                future,
                duplicate,
                regressed,
                cross_day,
                not ok_price,
                ok_price and not ok_ba,
                not ok_volume,
                volume_reg,
            )
        )
        if structural_fail:
            status = QualityStatus.INVALID
        elif outlier:
            status = QualityStatus.QUARANTINED
        elif freshness is QualityStatus.STALE:
            status = QualityStatus.STALE
        elif (
            freshness is QualityStatus.WARNING or not session_active
        ):
            status = QualityStatus.WARNING
        else:
            status = QualityStatus.FRESH

        result = MarketDataQualityResult(
            symbol=quote.symbol,
            status=status,
            checks=checks,
            reasons=reasons,
            quote_age_ms=age_ms,
            latency_ms=quote.latency_ms,
            checked_at=now,
            allow_warning_trading=cfg.allow_warning_trading,
        )

        # ── state update (only clean quotes move the baselines) ─
        with self._lock:
            self._evaluated += 1
            if not result.passed:
                self._rejected += 1
                self._quarantine.record(quote, result)
            self._by_status[status.value] = (
                self._by_status.get(status.value, 0) + 1
            )
            # remember identity regardless (a duplicate stays a dup)
            self._seen[identity] = None
            if len(self._seen) > cfg.duplicate_window:
                self._seen.popitem(last=False)
            # baseline updates
            if not structural_fail:
                self._last_ts[quote.symbol] = quote.timestamp
                if ok_price and quote.last > 0 and not outlier:
                    self._last_price[quote.symbol] = quote.last
                if ok_volume:
                    self._last_volume[quote.symbol] = quote.volume
                    self._last_volume_day[quote.symbol] = (
                        self._cal.trading_date_of(quote.timestamp)
                    )
            self._last_result[quote.symbol] = result

        return result

    # ── read path ──────────────────────────────────────────────

    def last_result(self, symbol: str) -> Optional[MarketDataQualityResult]:
        """The most recent full verdict for a symbol."""
        with self._lock:
            return self._last_result.get(symbol)

    def stats(self) -> dict:
        with self._lock:
            return {
                "evaluated": self._evaluated,
                "rejected": self._rejected,
                "by_status": dict(self._by_status),
            }

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()
            self._last_ts.clear()
            self._last_volume.clear()
            self._last_volume_day.clear()
            self._last_price.clear()
            self._last_result.clear()
            self._evaluated = 0
            self._rejected = 0
            self._by_status.clear()
        self._quarantine.reset()

    # ── stateless derivation (display fallback) ────────────────

    def derive(
        self,
        quote: MarketQuote,
        *,
        now: Optional[datetime] = None,
    ) -> MarketDataQualityResult:
        """Stateless quality snapshot for read-path display.

        Covers the checks that need no cross-quote memory; used by
        the Dashboard when the write-path gate is not enabled
        (Phase 1 mock feed) so the UI still shows honest quality.
        """
        return self._derive_result(quote, now)

    def _derive_result(
        self,
        quote: MarketQuote,
        now: Optional[datetime] = None,
    ) -> MarketDataQualityResult:
        now = now or datetime.now(timezone.utc)
        cfg = self._cfg
        checks: dict[str, bool] = {}
        reasons: list[str] = []

        ok_symbol = (
            isinstance(quote.symbol, str)
            and quote.symbol.isdigit()
            and len(quote.symbol) == 6
        )
        checks["symbol"] = ok_symbol
        if not ok_symbol:
            reasons.append("INVALID_SYMBOL")

        ok_exchange = isinstance(quote.exchange, Exchange)
        checks["exchange"] = ok_exchange
        if not ok_exchange:
            reasons.append("INVALID_EXCHANGE")

        ts_ok = quote.timestamp.tzinfo is not None
        future = ts_ok and quote.timestamp > (
            now + timedelta(milliseconds=cfg.future_tolerance_ms)
        )
        checks["timestamp"] = ts_ok and not future
        if not ts_ok:
            reasons.append("TIMESTAMP_NOT_AWARE")
        elif future:
            reasons.append("FUTURE_TIMESTAMP")

        age_ms = int(quote.age_seconds(now) * 1000)
        freshness = _freshness_status(age_ms, cfg)
        checks["freshness"] = freshness is not QualityStatus.STALE

        ok_price = (
            quote.last >= 0 and quote.bid >= 0 and quote.ask >= 0
        )
        checks["price"] = ok_price
        if not ok_price:
            reasons.append("INVALID_PRICE")

        ok_ba = ok_price and quote.bid <= quote.ask
        checks["bid_ask"] = ok_ba
        if ok_price and not ok_ba:
            reasons.append("CROSSED_BOOK")

        ok_volume = quote.volume >= 0 and quote.turnover >= 0
        checks["volume"] = ok_volume
        if not ok_volume:
            reasons.append("INVALID_VOLUME")

        try:
            session_active = self._cal.is_tradable(quote.timestamp)
        except Exception:
            session_active = False
        checks["session"] = session_active
        if not session_active:
            reasons.append("SESSION_INACTIVE")

        structural_fail = any(
            (not ok_symbol, not ok_exchange, not ts_ok, future,
             not ok_price, ok_price and not ok_ba, not ok_volume)
        )
        if structural_fail:
            status = QualityStatus.INVALID
        elif freshness is QualityStatus.STALE:
            status = QualityStatus.STALE
        elif freshness is QualityStatus.WARNING or not session_active:
            status = QualityStatus.WARNING
        else:
            status = QualityStatus.FRESH

        return MarketDataQualityResult(
            symbol=quote.symbol,
            status=status,
            checks=checks,
            reasons=reasons,
            quote_age_ms=age_ms,
            latency_ms=quote.latency_ms,
            checked_at=now,
            allow_warning_trading=cfg.allow_warning_trading,
        )


__all__ = ["QualityGate"]
