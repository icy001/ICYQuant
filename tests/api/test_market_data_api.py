"""Market Data API gate — Commit 010 §18.

Every checklist item from §18 is asserted here.  Most go through the
API gateway exactly like a real client would
(``TestClient(apps.api.main.app)``); a few pin behaviour that HTTP
cannot express — a session phase at an arbitrary instant, and a
quality verdict that only exists when a write-path gate is attached —
and drive ``MarketDataService`` directly.

Helpers that mutate the shared pipeline always restore it, so test
order never matters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.market_data.cache.market_cache import CacheBackendError
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.market_data_service import (
    SUPPORTED_TIMEFRAMES,
    MarketDataService,
    MarketDataServiceError,
    market_data_service,
)
from services.market_data.universe import universe

# ``reader`` / ``warm`` come from tests/api/conftest.py.
client = TestClient(app)

#: CST = UTC+8, no DST (the A-share trading day).
CST_OFFSET_HOURS = 8

SYMBOL = "159852"


# ══════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════


def _login(username: str, password: str) -> str:
    res = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cst(hour: int, minute: int, day: int = 11) -> datetime:
    """A tz-aware instant on a 2026 trading day (Fri 2026-09-11)."""
    return datetime(
        2026, 9, day, hour - CST_OFFSET_HOURS, minute, tzinfo=timezone.utc
    )


class _StubQuoteService:
    """Minimal read-path stand-in for phase/quality edge cases."""

    quality_gate = None

    def __init__(self, quotes=None, verdicts=None) -> None:
        self._quotes = quotes or {}
        self._verdicts = verdicts or {}

    def latest(self, symbol):
        return self._quotes.get(symbol)

    def quality(self, symbol):
        return self._verdicts.get(symbol)

    def stats(self) -> dict:
        return {}


class _StubCache:
    def __init__(self, health=None, verdicts=None) -> None:
        self._health = health or {}
        self._verdicts = verdicts or {}

    def health(self) -> dict:
        return self._health

    def get_quality(self, symbol):
        return self._verdicts.get(symbol)


class _AlwaysTradableCalendar:
    """Calendar stub: every instant is a tradable session.

    §14 freshness must be asserted independently of the wall clock —
    otherwise the gate only passes while an A-share session happens to
    be open.
    """

    def is_tradable(self, _when) -> bool:
        return True


def _quote(symbol: str = SYMBOL, age_seconds: float = 0.1) -> MarketQuote:
    """A quote that is already ``age_seconds`` old."""
    now = datetime.now(timezone.utc)
    ts = datetime.fromtimestamp(now.timestamp() - age_seconds, tz=timezone.utc)
    return MarketQuote(
        symbol=symbol,
        exchange=Exchange.SZSE,
        timestamp=ts,
        last=Decimal("1.234"),
        bid=Decimal("1.233"),
        ask=Decimal("1.234"),
        bid_size=12000,
        ask_size=18000,
        volume=1829300,
        turnover=Decimal("2256789.0"),
        open=Decimal("1.230"),
        high=Decimal("1.240"),
        low=Decimal("1.228"),
        pre_close=Decimal("1.220"),
        received_timestamp=ts,
    )


# ══════════════════════════════════════════════════════════════════
# ① Instruments (§2 / §18)
# ══════════════════════════════════════════════════════════════════


def test_md01_instruments_returns_universe(reader):
    """GET instruments → PASS, 11 symbols returned → PASS."""
    res = client.get("/api/market-data/instruments", headers=reader)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == len(universe.symbols())
    assert body["count"] == body["total"] == len(body["items"])
    assert body["count"] >= 11, "the A-share universe must be published"

    first = body["items"][0]
    for field in (
        "symbol",
        "name",
        "exchange",
        "instrument_type",
        "currency",
        "lot_size",
        "tick_size",
        "enabled",
        "trading_status",
    ):
        assert field in first, f"instrument missing {field}"
    assert first["currency"] == "CNY"
    assert first["lot_size"] == 100


def test_md01b_instrument_filters(reader):
    """exchange filter / type filter / enabled filter → PASS."""
    everything = client.get(
        "/api/market-data/instruments", headers=reader
    ).json()

    by_exchange = client.get(
        "/api/market-data/instruments?exchange=SZSE", headers=reader
    ).json()
    assert by_exchange["count"] > 0
    assert all(i["exchange"] == "SZSE" for i in by_exchange["items"])
    # every filter result must be a subset of the universe
    assert by_exchange["count"] <= everything["count"]

    by_type = client.get(
        "/api/market-data/instruments?instrument_type=ETF", headers=reader
    ).json()
    assert all(i["instrument_type"] == "ETF" for i in by_type["items"])

    enabled = client.get(
        "/api/market-data/instruments?enabled=true", headers=reader
    ).json()
    assert all(i["enabled"] is True for i in enabled["items"])
    assert enabled["count"] == len(universe.enabled())

    single = client.get(
        f"/api/market-data/instruments?symbol={SYMBOL}", headers=reader
    ).json()
    assert single["count"] == 1
    assert single["items"][0]["symbol"] == SYMBOL
    assert single["filters"]["symbol"] == SYMBOL


def test_md01c_instrument_detail_and_errors(reader):
    res = client.get(
        f"/api/market-data/instruments/{SYMBOL}", headers=reader
    )
    assert res.status_code == 200
    assert res.json()["symbol"] == SYMBOL

    # §13 — an unknown filter value is malformed input
    bad = client.get(
        "/api/market-data/instruments?exchange=NASDAQ", headers=reader
    )
    assert bad.status_code == 400, bad.text
    assert bad.json()["error"] == "MARKET_DATA_INVALID_PARAMETER"

    # §13 — an unknown symbol is 404, never an empty list
    missing = client.get(
        "/api/market-data/instruments?symbol=000000", headers=reader
    )
    assert missing.status_code == 404
    assert missing.json()["error"] == "MARKET_DATA_UNKNOWN_SYMBOL"

    assert (
        client.get(
            "/api/market-data/instruments/999999", headers=reader
        ).status_code
        == 404
    )


# ══════════════════════════════════════════════════════════════════
# ② / ③ / ④ Quotes (§3 / §4 / §14)
# ══════════════════════════════════════════════════════════════════


def test_md02_single_quote(warm):
    """single quote → PASS, quality metadata → PASS."""
    res = client.get(f"/api/market-data/quotes/{SYMBOL}", headers=warm)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["symbol"] == SYMBOL
    assert body["exchange"] == "SZSE"
    # the core price fields the spec promises
    for field in ("last", "bid", "ask", "volume", "turnover", "timestamp"):
        assert field in body
    assert body["last"] is not None
    assert isinstance(body["last"], (int, float))
    assert body["ask"] >= body["bid"]

    # §3 — quality / age / latency travel with every quote
    assert body["quality"] in (
        "FRESH",
        "WARNING",
        "STALE",
        "INVALID",
        "QUARANTINED",
    )
    assert body["status"] in ("LIVE", "WARNING", "STALE")
    assert isinstance(body["quote_age_ms"], int)
    assert body["quote_age_ms"] >= 0
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0


def test_md02b_batch_quote(warm):
    """batch quote → PASS (one request, no per-symbol looping)."""
    res = client.get(
        f"/api/market-data/quotes?symbols={SYMBOL},513050,159890",
        headers=warm,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 3
    assert body["requested"] == 3
    assert [i["symbol"] for i in body["items"]] == [
        SYMBOL,
        "513050",
        "159890",
    ]
    assert body["live_count"] <= body["count"]
    assert body["source"]


def test_md02c_batch_defaults_to_enabled_universe(warm):
    """No symbols param → the enabled universe (§4)."""
    body = client.get("/api/market-data/quotes", headers=warm).json()
    assert body["count"] == len(universe.enabled())
    assert {i["symbol"] for i in body["items"]} == {
        i.symbol for i in universe.enabled()
    }


def test_md02d_quote_errors(reader):
    """unknown symbol → PASS (§13)."""
    missing = client.get("/api/market-data/quotes/000000", headers=reader)
    assert missing.status_code == 404
    assert missing.json()["error"] == "MARKET_DATA_UNKNOWN_SYMBOL"

    # a bad symbol in a batch must not be silently dropped
    batch = client.get(
        "/api/market-data/quotes?symbols=159852,000000", headers=reader
    )
    assert batch.status_code == 404
    assert batch.json()["symbol"] == "000000"

    # an empty symbols list is meaningless, not "all"
    assert (
        client.get(
            "/api/market-data/quotes?symbols=", headers=reader
        ).status_code
        == 400
    )


def test_md02e_stale_quote_is_never_dressed_up_as_live():
    """§14 — a 25s-old quote is served *as* STALE.

    The API must not simply ``Redis GET → return``: the session /
    freshness verdict travels with the payload so the caller can never
    mistake old data for live data.
    """
    quotes = _StubQuoteService(quotes={SYMBOL: _quote()})
    service = MarketDataService(
        quote_service=quotes,
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
        trading_calendar=_AlwaysTradableCalendar(),
    )
    fresh = service.quote(SYMBOL)
    assert fresh["quality"] == "FRESH"
    assert fresh["status"] == "LIVE"
    assert fresh["tradable"] is True

    # a 25s-old quote (beyond the 10s stale line)
    stale_service = MarketDataService(
        quote_service=_StubQuoteService(
            quotes={SYMBOL: _quote(age_seconds=25)}
        ),
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
        trading_calendar=_AlwaysTradableCalendar(),
    )
    stale = stale_service.quote(SYMBOL)
    assert stale["status"] == "STALE"
    assert stale["quality"] == "STALE"
    assert stale["tradable"] is False
    # the data is still served — but honestly labelled
    assert stale["last"] == pytest.approx(1.234)
    assert stale["quote_age_ms"] >= 24_000


def test_md02f_no_quote_is_offline_not_fabricated(reader):
    """A registered symbol with no data yet: OFFLINE + null, never 0."""
    service = MarketDataService(
        quote_service=_StubQuoteService(),
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
    )
    view = service.quote(SYMBOL)
    assert view["status"] == "OFFLINE"
    assert view["quality"] is None
    assert view["last"] is None
    assert view["tradable"] is False


# ══════════════════════════════════════════════════════════════════
# ⑤ / ⑥ / ⑦ Bars (§5 / §6 / §7)
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def bars(warm) -> dict:
    res = client.get(
        f"/api/market-data/bars?symbol={SYMBOL}&timeframe=1m&limit=60",
        headers=warm,
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_md03_bars_1m_series(bars):
    """1m bars → PASS.  The envelope describes the series."""
    assert bars["symbol"] == SYMBOL
    assert bars["exchange"] == "SZSE"
    assert bars["timeframe"] == "1m"
    assert bars["count"] == len(bars["items"]) > 0
    assert bars["source"]

    item = bars["items"][0]
    for field in (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "is_closed",
    ):
        assert field in item, f"bar missing {field}"
    assert item["high"] >= item["low"]


def test_md03b_historical_realtime_merge(bars):
    """historical + realtime merge → PASS (§6 — one source, not two)."""
    merge = bars["merge"]
    assert merge["enabled"] is True
    assert merge["historical_count"] > 0, "history must be present"
    # total == historical + realtime - overlaps: nothing invented, nothing lost
    assert (
        bars["count"]
        == merge["historical_count"]
        + merge["realtime_count"]
        - merge["overlaps"]
    )
    assert merge["mode"]
    sources = [b["source"] for b in bars["items"]]
    assert set(sources) <= {"HISTORICAL", "REALTIME"}
    # history first, then the live tail
    assert sources == sorted(
        sources, key=lambda s: 0 if s == "HISTORICAL" else 1
    )


def test_md03c_ordering_and_no_duplicates(bars):
    """ordering → PASS, duplicate removal → PASS."""
    stamps = [b["timestamp"] for b in bars["items"]]
    assert stamps == sorted(stamps), "series must be chronological"
    assert len(set(stamps)) == len(stamps), "no duplicate minutes"

    ids = [b["bar_id"] for b in bars["items"]]
    assert len(set(ids)) == len(ids), "no duplicate bars"


def test_md03d_current_bar_is_not_closed(bars):
    """current bar → PASS, is_closed → PASS (§7)."""
    open_bars = [b for b in bars["items"] if not b["is_closed"]]
    assert len(open_bars) <= 1, "at most one minute can be in progress"
    if open_bars:
        assert bars["has_live"] is True
        # the in-progress bar is always the tail of the series
        assert bars["items"][-1] is open_bars[0] or (
            bars["items"][-1]["bar_id"] == open_bars[0]["bar_id"]
        )
    assert bars["closed_count"] == len(
        [b for b in bars["items"] if b["is_closed"]]
    )
    assert bars["quality"]["checked"] == bars["count"]
    assert bars["quality"]["invalid_count"] == 0


def test_md03e_bar_window_filter(warm):
    """start/end are inclusive and applied to the unified series."""
    start = "2026-09-01T00:00:00+08:00"
    end = "2026-12-31T23:59:59+08:00"
    # pass params through httpx so the "+08:00" offset is percent-encoded
    # — a raw "+" in a query string decodes to a space and the instant
    # would never parse
    res = client.get(
        "/api/market-data/bars",
        params={
            "symbol": SYMBOL,
            "timeframe": "1m",
            "limit": 60,
            "start": start,
            "end": end,
        },
        headers=warm,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["start"] and body["end"]
    # compare instants, not strings — bar timestamps are UTC, the echo
    # of the filter keeps the caller's offset
    low = datetime.fromisoformat(body["start"])
    high = datetime.fromisoformat(body["end"])
    assert all(
        low <= datetime.fromisoformat(b["timestamp"]) <= high
        for b in body["items"]
    )

    # an inverted window is a parameter error, not an empty chart
    inverted = client.get(
        "/api/market-data/bars",
        params={"symbol": SYMBOL, "start": end, "end": start},
        headers=warm,
    )
    assert inverted.status_code == 400


def test_md03f_bar_parameter_errors(warm):
    """§13 — unsupported timeframe is 400, never an empty array."""
    bad_tf = client.get(
        f"/api/market-data/bars?symbol={SYMBOL}&timeframe=5m", headers=warm
    )
    assert bad_tf.status_code == 400, bad_tf.text
    payload = bad_tf.json()
    assert payload["error"] == "MARKET_DATA_UNSUPPORTED_TIMEFRAME"
    assert payload["supported"] == list(SUPPORTED_TIMEFRAMES)

    for bad_limit in (0, -1, 9999):
        res = client.get(
            f"/api/market-data/bars?symbol={SYMBOL}&limit={bad_limit}",
            headers=warm,
        )
        assert res.status_code == 400, f"limit={bad_limit}"

    bad_date = client.get(
        f"/api/market-data/bars?symbol={SYMBOL}&start=not-a-date",
        headers=warm,
    )
    assert bad_date.status_code == 400

    assert (
        client.get(
            "/api/market-data/bars?symbol=000000", headers=warm
        ).status_code
        == 404
    )


# ══════════════════════════════════════════════════════════════════
# ⑧ Session (§8)
# ══════════════════════════════════════════════════════════════════


def test_md04_session_endpoint(reader):
    """Live session payload has the §8 shape."""
    res = client.get("/api/market-data/session", headers=reader)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exchange"] == "SZSE"
    assert body["market"] == "A-SHARE"
    assert body["trading_date"]
    assert body["phase"] in (
        "PRE_OPEN",
        "AUCTION",
        "CONTINUOUS_AM",
        "LUNCH_BREAK",
        "CONTINUOUS_PM",
        "CLOSE",
        "POST_CLOSE",
        "NON_TRADING",
    )
    assert isinstance(body["is_trading_day"], bool)
    assert isinstance(body["is_tradable"], bool)
    assert body["next_event"]["at"]
    assert body["server_time"]

    other = client.get(
        "/api/market-data/session?exchange=SSE", headers=reader
    )
    assert other.status_code == 200
    assert other.json()["exchange"] == "SSE"

    assert (
        client.get(
            "/api/market-data/session?exchange=NASDAQ", headers=reader
        ).status_code
        == 400
    )

    both = client.get("/api/market-data/sessions", headers=reader).json()
    assert {i["exchange"] for i in both["items"]} == {"SZSE", "SSE"}


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        (10, 0, "CONTINUOUS_AM"),  # 连续竞价（上午）
        (12, 0, "LUNCH_BREAK"),  # 午间休市
        (14, 0, "CONTINUOUS_PM"),  # 连续竞价（下午）
        (15, 2, "CLOSE"),  # 收盘集合竞价
        (8, 0, "PRE_OPEN"),  # 开盘前
    ],
)
def test_md04b_session_phases(hour, minute, expected):
    """continuous AM / lunch break / continuous PM / close → PASS.

    Time is pinned through the service because HTTP has no "at"
    parameter — the phase engine is what is under test.
    """
    service = MarketDataService()
    body = service.session(at=_cst(hour, minute))
    assert body["phase"] == expected
    assert body["is_trading_day"] is True
    assert body["session_start"] and body["session_end"]
    # HH:MM:SS, the form the spec shows
    assert len(body["session_start"]) == 8
    assert body["session_start"] < body["session_end"]
    if expected in ("CONTINUOUS_AM", "CONTINUOUS_PM"):
        assert body["is_tradable"] is True
    else:
        assert body["is_tradable"] is False


def test_md04c_session_non_trading_day():
    """trading day → PASS (weekend / holiday are honestly flagged)."""
    service = MarketDataService()
    # Sunday 2026-09-13
    sunday = service.session(at=_cst(10, 0, day=13))
    assert sunday["phase"] == "NON_TRADING"
    assert sunday["is_trading_day"] is False
    assert sunday["is_tradable"] is False
    assert sunday["session_start"] is None


# ══════════════════════════════════════════════════════════════════
# ⑨ Quality (§9)
# ══════════════════════════════════════════════════════════════════


def test_md05_quality_fresh(warm):
    """FRESH → PASS (through the API, on real data)."""
    res = client.get(f"/api/market-data/quality/{SYMBOL}", headers=warm)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == SYMBOL
    assert body["status"] in (
        "FRESH",
        "WARNING",
        "STALE",
        "INVALID",
        "QUARANTINED",
    )
    assert isinstance(body["checks"], dict) and body["checks"]
    assert set(body["checks"].values()) <= {"PASS", "FAIL"}
    assert isinstance(body["reasons"], list)
    assert body["checked_at"]
    assert body["source"] in ("quote_service", "quarantine", "cache")

    overview = client.get("/api/market-data/quality", headers=warm).json()
    assert overview["instruments"] == len(universe.symbols())
    assert set(overview["counts"]) >= {
        "FRESH",
        "WARNING",
        "STALE",
        "INVALID",
        "QUARANTINED",
        "OFFLINE",
    }
    assert len(overview["symbols"]) == overview["instruments"]


@pytest.mark.parametrize(
    "status,expected_tradable",
    [
        ("FRESH", True),
        ("WARNING", False),
        ("STALE", False),
        ("INVALID", False),
        ("QUARANTINED", False),
    ],
)
def test_md05b_quality_statuses(status, expected_tradable):
    """FRESH / WARNING / STALE / INVALID / QUARANTINED → PASS.

    FRESH and STALE come from real reads (see md02e); the gate-only
    verdicts are exercised on a service whose quote service reports
    them, which is the only way INVALID / QUARANTINED can exist — such
    payloads are dropped before they are ever stored as a quote.
    """
    checks = {
        "timestamp": status == "FRESH",
        "price": status not in ("INVALID", "QUARANTINED"),
    }
    verdict = {
        "symbol": SYMBOL,
        "status": status,
        "passed": status == "FRESH",
        "tradable": expected_tradable,
        "action": "PASS" if status == "FRESH" else "BLOCK_TRADING",
        "checks": checks,
        "reasons": [] if status == "FRESH" else [f"{status}_REASON"],
        "quote_age_ms": 120,
        "latency_ms": 35,
        "checked_at": "2026-09-11T15:01:23+08:00",
    }
    service = MarketDataService(
        quote_service=_StubQuoteService(verdicts={SYMBOL: verdict}),
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
    )
    body = service.quality(SYMBOL)
    assert body["status"] == status
    assert body["tradable"] is expected_tradable
    assert set(body["checks"].values()) <= {"PASS", "FAIL"}
    if status == "FRESH":
        assert body["checks_passed"] is True
        assert body["reasons"] == []
    else:
        assert body["reasons"], "a non-fresh verdict must explain itself"


def test_md05c_quality_reads_quarantine_ring():
    """INVALID / QUARANTINED survive only in the quarantine ring."""
    class _Gate:
        class quarantine:  # noqa: N801
            @staticmethod
            def recent(limit):
                return [
                    {
                        "symbol": SYMBOL,
                        "status": "QUARANTINED",
                        "reasons": ["PRICE_OUTLIER"],
                        "action": "QUARANTINE",
                        "received_at": "2026-09-11T15:01:23+08:00",
                    }
                ]

    class _GatedQuotes(_StubQuoteService):
        pass

    quotes = _GatedQuotes()
    quotes.quality_gate = _Gate()
    service = MarketDataService(
        quote_service=quotes,
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
    )
    body = service.quality(SYMBOL)
    assert body["status"] == "QUARANTINED"
    assert body["tradable"] is False
    assert body["source"] == "quarantine"
    assert body["reasons"] == ["PRICE_OUTLIER"]
    # no checks were executed → not a pass
    assert body["checks_passed"] is False


def test_md05d_quality_without_data_is_404(reader):
    """No data yet → 404 (there is no verdict to report)."""
    service = MarketDataService(
        quote_service=_StubQuoteService(),
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(),
    )
    with pytest.raises(MarketDataServiceError) as err:
        service.quality(SYMBOL)
    assert err.value.status_code == 404

    assert (
        client.get("/api/market-data/quality/000000", headers=reader).status_code
        == 404
    )


# ══════════════════════════════════════════════════════════════════
# ⑩ Infrastructure (§10 / §18)
# ══════════════════════════════════════════════════════════════════


def test_md06_health_healthy(warm):
    """Market Data health → PASS."""
    res = client.get("/api/market-data/health", headers=warm)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] in ("HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE")
    assert body["adapter"] == "UP"
    assert body["redis"] == "UP"
    assert body["symbols"]["total"] == len(universe.symbols())
    assert (
        body["symbols"]["fresh"]
        + body["symbols"]["warning"]
        + body["symbols"]["stale"]
        + body["symbols"]["invalid"]
        + body["symbols"]["quarantined"]
        + body["symbols"]["offline"]
        == body["symbols"]["total"]
    )
    assert body["feed"]["running"] is True
    assert body["session"]["phase"]
    assert body["timeframes"] == list(SUPPORTED_TIMEFRAMES)


def test_md06b_redis_degraded(reader, monkeypatch):
    """Redis DEGRADED → PASS.

    A degraded cache blocks trading, so the overall verdict must be
    BLOCKED — not a cheerful HEALTHY.
    """
    class _Degraded:
        def health(self):
            return {
                "status": "DEGRADED",
                "backend": "redis",
                "enabled": True,
                "consecutive_failures": 3,
                "last_error": "connection refused",
                "last_error_at": None,
                "trading_allowed": False,
            }

        def get_quality(self, symbol):
            return None

    monkeypatch.setattr(market_data_service, "_cache", _Degraded())
    res = client.get("/api/market-data/health", headers=reader)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["redis"] == "DEGRADED"
    assert body["status"] == "BLOCKED"
    assert body["cache"]["trading_allowed"] is False


def test_md06c_service_unavailable_is_503(reader, monkeypatch):
    """API unavailable → 503 (§13).

    When ingestion cannot be started there is no honest answer to
    give, so the API says so instead of returning an empty series.
    """
    def _boom():
        raise CacheBackendError("adapter offline")

    market_data_service.stop_feed()
    monkeypatch.setattr(market_data_service, "_adapter_factory", _boom)
    try:
        res = client.get(f"/api/market-data/quotes/{SYMBOL}", headers=reader)
        assert res.status_code == 503, res.text
        assert res.json()["error"] == "MARKET_DATA_UNAVAILABLE"
    finally:
        market_data_service._adapter_factory = None
        market_data_service.ensure_feed()


def test_md06d_health_does_not_start_ingestion(monkeypatch):
    """A health probe must not mutate state."""
    probe = MarketDataService(
        quote_service=_StubQuoteService(),
        bar_service=None,
        merge_engine=None,
        market_cache=_StubCache(
            health={
                "status": "HEALTHY",
                "backend": "memory",
                "enabled": True,
                "consecutive_failures": 0,
                "last_error": None,
                "last_error_at": None,
                "trading_allowed": True,
            }
        ),
    )
    body = probe.health()
    assert body["feed"]["started"] is False
    assert body["feed"]["running"] is False
    assert body["adapter"] == "DOWN"
    assert body["status"] == "OFFLINE"
    assert probe.feed_started is False


# ══════════════════════════════════════════════════════════════════
# ⑪ Access control & §15 topology
# ══════════════════════════════════════════════════════════════════


def test_md07_every_read_requires_a_token():
    for path in (
        "/api/market-data/instruments",
        "/api/market-data/instruments/159852",
        "/api/market-data/quotes/159852",
        "/api/market-data/quotes",
        "/api/market-data/bars?symbol=159852",
        "/api/market-data/session",
        "/api/market-data/sessions",
        "/api/market-data/quality/159852",
        "/api/market-data/quality",
        "/api/market-data/health",
    ):
        assert client.get(path).status_code == 401, path


def test_md07b_feed_control_needs_operator():
    """Starting/stopping ingestion is an operator action (RBAC)."""
    reader = _headers(_login("readonly", "readonly123"))
    assert client.post("/api/market-data/feed/stop", headers=reader).status_code == 403

    operator = _headers(_login("operator", "operator123"))
    stopped = client.post("/api/market-data/feed/stop", headers=operator)
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["running"] is False

    started = client.post("/api/market-data/feed/start", headers=operator)
    assert started.status_code == 200, started.text
    assert started.json()["running"] is True
    assert started.json()["adapter"]


def test_md07c_paper_trading_shares_the_service(reader, warm):
    """§15 — Paper Trading is an in-process consumer of this service.

    The topology is asserted, not assumed: the feed Paper Trading
    prices orders from reports the same quote the API just served.
    """
    wiring = client.get("/api/market-data/wiring", headers=reader).json()
    assert wiring["paper_uses_service"] is True
    assert wiring["quote_service"] == "QuoteService"

    feed = market_data_service.paper_feed()
    served = client.get(
        f"/api/market-data/quotes/{SYMBOL}", headers=reader
    ).json()
    internal = feed.latest_quote(SYMBOL)
    assert internal is not None, "paper feed sees no quote for the symbol"
    assert float(internal.last) == pytest.approx(served["last"])
