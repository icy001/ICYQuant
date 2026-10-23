"""Market Data API contract gate — Commit 010 §19.

§19 is explicit that the valuable thing is not "the endpoint responds"
but "**the contract is stable**".  Commits 011 (Dashboard), 013
(Monitoring) and 014 (Broker) all build on this surface, so every
promise is pinned:

* status codes
* JSON schema (the exact field set — additive changes must be
  deliberate, removals must break here)
* required fields
* field types
* enum values
* error responses

Two layers are checked.  The wire layer replays real responses through
the Pydantic models; the type layer proves the enums actually *reject*
bad values rather than merely documenting them (a contract that cannot
fail is not a contract).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.schemas.market_data import (
    BarSeriesResponse,
    ErrorResponse,
    HealthResponse,
    InstrumentListResponse,
    InstrumentResponse,
    MarketDataWiringResponse,
    QualityOverviewResponse,
    QualityResponse,
    QuoteListResponse,
    QuoteResponse,
    SessionListResponse,
    SessionResponse,
)

SYMBOL = "159852"


# ══════════════════════════════════════════════════════════════════
# Field sets — the printed contract
# ══════════════════════════════════════════════════════════════════


def test_ct01_declared_field_sets():
    """Removing or renaming a field must fail here first."""
    assert set(QuoteResponse.model_fields) == {
        "symbol",
        "name",
        "exchange",
        "instrument_type",
        "currency",
        "lot_size",
        "tick_size",
        # §3 quality metadata
        "status",
        "quality",
        "tradable",
        # §3 prices & sizes
        "last",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "volume",
        "turnover",
        "open",
        "high",
        "low",
        "pre_close",
        "change",
        "change_pct",
        "spread",
        # §3 timing
        "timestamp",
        "received_timestamp",
        "quote_age_ms",
        "latency_ms",
    }

    assert set(InstrumentResponse.model_fields) == {
        "symbol",
        "name",
        "exchange",
        "instrument_type",
        "currency",
        "lot_size",
        "tick_size",
        "enabled",
        "trading_status",
    }

    assert set(QuoteListResponse.model_fields) == {
        "items",
        "count",
        "requested",
        "live_count",
        "source",
    }

    assert set(HealthResponse.model_fields) == {
        "status",
        "adapter",
        "redis",
        "quality",
        "symbols",
        "instruments",
        "feed",
        "cache",
        "session",
        "timeframes",
        "server_time",
        "checked_at",
    }

    assert set(SessionResponse.model_fields) == {
        "exchange",
        "market",
        "trading_date",
        "phase",
        "phase_label",
        "session_start",
        "session_end",
        "session_start_at",
        "session_end_at",
        "is_trading_day",
        "is_tradable",
        "next_event",
        "server_time",
        "timezone",
    }

    assert set(QualityResponse.model_fields) == {
        "symbol",
        "name",
        "status",
        "tradable",
        "passed",
        "action",
        "checks",
        "checks_passed",
        "reasons",
        "quote_age_ms",
        "latency_ms",
        "checked_at",
        "source",
        "config",
    }

    assert set(ErrorResponse.model_fields) == {
        "error",
        "detail",
        "parameter",
        "value",
        "allowed",
    }


def test_ct02_bar_item_field_set():
    item = BarSeriesResponse.model_fields["items"].annotation
    # list[BarResponse]
    bar_model = item.__args__[0]
    assert set(bar_model.model_fields) == {
        "symbol",
        "exchange",
        "timeframe",
        "timestamp",
        "bar_id",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "change",
        "change_pct",
        "is_closed",
        "source",
    }


# ══════════════════════════════════════════════════════════════════
# Wire layer — real responses must satisfy the models
# ══════════════════════════════════════════════════════════════════


def test_ct03_instruments_payload_matches_schema(gateway, reader):
    res = gateway.get("/api/market-data/instruments", headers=reader)
    assert res.status_code == 200
    model = InstrumentListResponse.model_validate(res.json())
    assert model.count == len(model.items)
    assert model.total >= model.count
    for item in model.items:
        assert item.exchange in ("SZSE", "SSE")
        assert item.instrument_type in ("ETF", "QDII-ETF", "LOF", "QDII-LOF")
        assert isinstance(item.lot_size, int) and item.lot_size > 0
        assert isinstance(item.tick_size, float)


def test_ct04_quote_payload_matches_schema(gateway, warm):
    """A served quote satisfies QuoteResponse, types included."""
    res = gateway.get(f"/api/market-data/quotes/{SYMBOL}", headers=warm)
    assert res.status_code == 200
    raw = res.json()
    model = QuoteResponse.model_validate(raw)

    assert model.symbol == SYMBOL
    # prices travel as JSON numbers, not strings (§12 sketch)
    assert isinstance(raw["last"], (int, float))
    assert isinstance(raw["bid"], (int, float))
    assert isinstance(raw["ask"], (int, float))
    assert isinstance(raw["volume"], int)
    assert isinstance(raw["quote_age_ms"], int)
    assert isinstance(raw["latency_ms"], int)
    assert isinstance(raw["tradable"], bool)
    # timestamps are ISO-8601 with an offset
    assert "T" in raw["timestamp"] and (
        "+" in raw["timestamp"] or raw["timestamp"].endswith("Z")
    )


def test_ct05_batch_quote_payload_matches_schema(gateway, warm):
    res = gateway.get(f"/api/market-data/quotes?symbols={SYMBOL}", headers=warm)
    model = QuoteListResponse.model_validate(res.json())
    assert model.count == len(model.items)
    assert model.requested == model.count == 1


def test_ct06_bars_payload_matches_schema(gateway, warm):
    res = gateway.get(
        f"/api/market-data/bars?symbol={SYMBOL}&timeframe=1m&limit=30",
        headers=warm,
    )
    assert res.status_code == 200
    model = BarSeriesResponse.model_validate(res.json())
    assert model.count == len(model.items)
    assert model.timeframe == "1m"
    for bar in model.items:
        assert bar.source in ("HISTORICAL", "REALTIME")
        assert bar.is_closed in (True, False)
        assert bar.high >= bar.low
        assert bar.timeframe == "1m"


def test_ct07_session_payload_matches_schema(gateway, reader):
    res = gateway.get("/api/market-data/session", headers=reader)
    assert res.status_code == 200
    model = SessionResponse.model_validate(res.json())
    assert model.exchange == "SZSE"
    assert model.phase in (
        "PRE_OPEN",
        "AUCTION",
        "CONTINUOUS_AM",
        "LUNCH_BREAK",
        "CONTINUOUS_PM",
        "CLOSE",
        "POST_CLOSE",
        "NON_TRADING",
    )
    # HH:MM:SS when the segment exists, null off-session
    if model.session_start is not None:
        assert len(model.session_start) == 8
        assert len(model.session_end) == 8

    both = gateway.get("/api/market-data/sessions", headers=reader)
    SessionListResponse.model_validate(both.json())


def test_ct08_quality_payload_matches_schema(gateway, warm):
    res = gateway.get(f"/api/market-data/quality/{SYMBOL}", headers=warm)
    assert res.status_code == 200
    raw = res.json()
    model = QualityResponse.model_validate(raw)
    assert model.status in ("FRESH", "WARNING", "STALE", "INVALID", "QUARANTINED")
    assert model.source in ("quote_service", "quarantine", "cache")
    # checks are labelled PASS/FAIL, never raw booleans on the wire
    for value in raw["checks"].values():
        assert value in ("PASS", "FAIL")

    overview = gateway.get("/api/market-data/quality", headers=warm)
    QualityOverviewResponse.model_validate(overview.json())


def test_ct09_health_payload_matches_schema(gateway, warm):
    res = gateway.get("/api/market-data/health", headers=warm)
    assert res.status_code == 200
    raw = res.json()
    model = HealthResponse.model_validate(raw)
    assert model.status in ("HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE")
    assert model.redis in ("UP", "DOWN", "DEGRADED", "DISABLED", "UNKNOWN")
    assert model.quality in ("HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE")
    assert model.symbols.total == sum(
        [
            model.symbols.fresh,
            model.symbols.warning,
            model.symbols.stale,
            model.symbols.invalid,
            model.symbols.quarantined,
            model.symbols.offline,
        ]
    )
    assert raw["feed"]["stats"] is not None

    wiring = gateway.get("/api/market-data/wiring", headers=warm)
    MarketDataWiringResponse.model_validate(wiring.json())


# ══════════════════════════════════════════════════════════════════
# Type layer — the enums must actually reject
# ══════════════════════════════════════════════════════════════════


def _valid_quote() -> dict:
    return {
        "symbol": SYMBOL,
        "name": "软件ETF嘉实",
        "exchange": "SZSE",
        "instrument_type": "ETF",
        "currency": "CNY",
        "lot_size": 100,
        "tick_size": 0.001,
        "status": "LIVE",
        "quality": "FRESH",
        "tradable": True,
        "last": 1.234,
        "bid": 1.233,
        "ask": 1.234,
        "bid_size": 12000,
        "ask_size": 18000,
        "volume": 1829300,
        "turnover": 2256789.0,
        "timestamp": "2026-09-11T15:01:23+08:00",
        "received_timestamp": "2026-09-11T15:01:23.120+08:00",
        "quote_age_ms": 120,
        "latency_ms": 35,
    }


def test_ct10_quote_enum_and_type_rejection():
    """Bad enum values / wrong types must raise, not pass silently."""
    QuoteResponse.model_validate(_valid_quote())

    bad_status = {**_valid_quote(), "status": "BANANA"}
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate(bad_status)

    bad_quality = {**_valid_quote(), "quality": "MAYBE"}
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate(bad_quality)

    bad_exchange = {**_valid_quote(), "exchange": "NASDAQ"}
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate(bad_exchange)

    # a price arriving as a string is a contract break
    bad_type = {**_valid_quote(), "last": "1.234"}
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate(bad_type)

    # tradable must be a boolean, not a truthy string
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate({**_valid_quote(), "tradable": "yes"})

    # missing required field
    without_last = _valid_quote()
    del without_last["last"]
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate(without_last)


def test_ct10b_offline_quote_is_explicitly_nullable():
    """The one deliberate relaxation, and it is bounded.

    ``last`` is nullable *only* so an unserved symbol can report
    OFFLINE honestly; every price field must be null together.
    """
    offline = {
        **_valid_quote(),
        "status": "OFFLINE",
        "quality": None,
        "tradable": False,
        "last": None,
        "bid": None,
        "ask": None,
        "timestamp": None,
        "quote_age_ms": None,
    }
    model = QuoteResponse.model_validate(offline)
    assert model.status == "OFFLINE"
    assert model.last is None
    assert model.quality is None

    # OFFLINE is a valid status but "STALE" is not a live one
    with pytest.raises(ValidationError):
        QuoteResponse.model_validate({**offline, "status": "OPEN"})


def test_ct10c_health_and_session_enum_rejection():
    with pytest.raises(ValidationError):
        SessionResponse.model_validate(
            {
                "exchange": "SZSE",
                "market": "A-SHARE",
                "trading_date": "2026-09-11",
                "phase": "SIESTA",
                "phase_label": "x",
                "is_trading_day": True,
                "is_tradable": False,
                "next_event": {"phase": "CLOSE", "label": "x", "at": "now"},
                "server_time": "now",
                "timezone": "Asia/Shanghai (UTC+8)",
            }
        )


# ══════════════════════════════════════════════════════════════════
# Error responses (§13)
# ══════════════════════════════════════════════════════════════════


def test_ct11_error_envelope_400(gateway, reader):
    res = gateway.get(
        f"/api/market-data/bars?symbol={SYMBOL}&timeframe=5m", headers=reader
    )
    assert res.status_code == 400
    raw = res.json()
    # top-level envelope, not nested under "detail"
    assert "error" in raw and "detail" in raw
    model = ErrorResponse.model_validate(raw)
    assert model.error == "MARKET_DATA_UNSUPPORTED_TIMEFRAME"
    assert model.parameter == "timeframe"
    assert model.value == "5m"
    assert model.allowed == ["1m"]


def test_ct12_error_envelope_404(gateway, reader):
    res = gateway.get("/api/market-data/quotes/000000", headers=reader)
    assert res.status_code == 404
    model = ErrorResponse.model_validate(res.json())
    assert model.error == "MARKET_DATA_UNKNOWN_SYMBOL"
    assert model.detail
    assert model.value == "000000"


def test_ct13_error_envelope_503(gateway, reader, monkeypatch):
    from services.market_data.market_data_service import market_data_service

    def _boom():
        raise RuntimeError("adapter offline")

    market_data_service.stop_feed()
    monkeypatch.setattr(market_data_service, "_adapter_factory", _boom)
    try:
        res = gateway.get(
            f"/api/market-data/bars?symbol={SYMBOL}", headers=reader
        )
        assert res.status_code == 503, res.text
        model = ErrorResponse.model_validate(res.json())
        assert model.error == "MARKET_DATA_UNAVAILABLE"
        assert model.detail
    finally:
        market_data_service._adapter_factory = None
        market_data_service.ensure_feed()


def test_ct14_unauthorized_is_not_the_error_envelope(gateway):
    """401 comes from the auth layer and keeps its own shape.

    Documented so a later commit does not "unify" it by accident: the
    §13 envelope covers 400/404/503 only.
    """
    res = gateway.get("/api/market-data/health")
    assert res.status_code == 401
    assert "error" not in res.json()


# ══════════════════════════════════════════════════════════════════
# OpenAPI registration
# ══════════════════════════════════════════════════════════════════


def test_ct15_routes_are_published_with_model_names(gateway):
    """Every §2–§10 endpoint is in the OpenAPI document.

    This is the strongest single check that the gateway advertises the
    contract rather than just returning JSON.
    """
    spec = gateway.get("/openapi.json").json()
    paths = spec["paths"]

    expected = {
        "/api/market-data/instruments": "InstrumentListResponse",
        "/api/market-data/instruments/{symbol}": "InstrumentResponse",
        "/api/market-data/quotes": "QuoteListResponse",
        "/api/market-data/quotes/{symbol}": "QuoteResponse",
        "/api/market-data/bars": "BarSeriesResponse",
        "/api/market-data/session": "SessionResponse",
        "/api/market-data/sessions": "SessionListResponse",
        "/api/market-data/quality": "QualityOverviewResponse",
        "/api/market-data/quality/{symbol}": "QualityResponse",
        "/api/market-data/health": "HealthResponse",
        "/api/market-data/wiring": "MarketDataWiringResponse",
    }
    for path, model_name in expected.items():
        assert path in paths, f"{path} is not registered"
        operation = paths[path]["get"]
        schema = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert model_name in str(schema), f"{path} → {schema}"

    # every documented component exists in components.schemas
    for model_name in list(expected.values()) + ["ErrorResponse"]:
        assert model_name in spec["components"]["schemas"], model_name


def test_ct16_error_responses_are_documented(gateway):
    spec = gateway.get("/openapi.json").json()
    bars = spec["paths"]["/api/market-data/bars"]["get"]["responses"]
    for code in ("400", "404", "503"):
        assert code in bars, f"bars does not document {code}"
        schema = bars[code]["content"]["application/json"]["schema"]
        assert "ErrorResponse" in str(schema)
