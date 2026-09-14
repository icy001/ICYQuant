"""Market Data API response models (Commit 010 §12).

Why explicit models instead of returning the service's dicts:

* the JSON field set and its **types** become a versioned contract
  (§19) that Dashboard / Strategy / external clients can depend on;
* a domain-model change surfaces here as a validation error in tests
  rather than as a silent wire-format change;
* enum-valued fields are narrowed with ``Literal`` so an unexpected
  value fails loudly instead of leaking out.

One deliberate deviation from the §12 sketch: price fields are
``Optional[float]`` rather than ``float``.  A registered symbol whose
quote has not arrived yet must be able to report ``OFFLINE`` with
``last = None`` — never a fabricated ``0``.  Every other field keeps
the spec's required-ness.

Prices travel as JSON numbers on the wire; the domain keeps ``Decimal``
and the service converts at the boundary.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── enums (narrow types for §19 field/enum validation) ────────────

ExchangeName = Literal["SZSE", "SSE"]

InstrumentTypeName = Literal["ETF", "QDII-ETF", "LOF", "QDII-LOF"]

TradingStatusName = Literal["NORMAL", "HALTED", "SUSPENDED", "DELISTED"]

QualityStatusName = Literal[
    "FRESH", "WARNING", "STALE", "INVALID", "QUARANTINED"
]

#: Display status of a quote: LIVE on a fresh verdict, otherwise the
#: verdict itself — plus OFFLINE when nothing has been received.
QuoteStatusName = Literal[
    "LIVE", "WARNING", "STALE", "INVALID", "QUARANTINED", "OFFLINE"
]

MarketPhaseName = Literal[
    "PRE_OPEN",
    "AUCTION",
    "CONTINUOUS_AM",
    "LUNCH_BREAK",
    "CONTINUOUS_PM",
    "CLOSE",
    "POST_CLOSE",
    "NON_TRADING",
]

HealthStatusName = Literal["HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE"]

ComponentStatusName = Literal[
    "UP", "DOWN", "DEGRADED", "DISABLED", "UNKNOWN"
]

#: Quality roll-up status: the five gate verdicts plus OFFLINE for a
#: registered symbol whose quote has not arrived yet.
QualityRollupStatusName = Literal[
    "FRESH", "WARNING", "STALE", "INVALID", "QUARANTINED", "OFFLINE"
]

CheckResult = Literal["PASS", "FAIL"]

BarSourceName = Literal["HISTORICAL", "REALTIME"]

GatewayActionName = Literal["PASS", "BLOCK_TRADING", "DROP", "QUARANTINE"]


# ── errors ────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Uniform error envelope for 400 / 404 / 503 (§13)."""

    error: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable explanation")
    parameter: Optional[str] = Field(
        default=None, description="Offending query parameter, if any"
    )
    value: Optional[str] = Field(
        default=None, description="Rejected value, if any"
    )
    allowed: Optional[list[str]] = Field(
        default=None, description="Accepted values, if any"
    )


# ── ① Instruments ─────────────────────────────────────────────────


class InstrumentResponse(BaseModel):
    symbol: str
    name: str
    exchange: ExchangeName
    instrument_type: InstrumentTypeName
    currency: str
    lot_size: int
    tick_size: Optional[float] = None
    enabled: bool
    trading_status: TradingStatusName


class InstrumentFilters(BaseModel):
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    instrument_type: Optional[str] = None
    enabled: Optional[bool] = None


class InstrumentListResponse(BaseModel):
    items: list[InstrumentResponse]
    count: int
    total: int = Field(description="Universe size before filtering")
    filters: InstrumentFilters
    exchanges: list[str]
    instrument_types: list[str]


# ── ② / ③ / ④ Quotes ─────────────────────────────────────────────


class QuoteResponse(BaseModel):
    #: Prices must never be *silently coerced*: pydantic's lax mode turns
    #: ``"1.234"`` into ``1.234`` and ``"yes"`` into ``True``, which would
    #: let a broken producer ship strings and still satisfy the contract.
    #: Strict mode makes the wire types part of the promise (§19).
    model_config = ConfigDict(strict=True)

    symbol: str
    name: str
    exchange: ExchangeName
    instrument_type: InstrumentTypeName
    currency: str
    lot_size: int
    tick_size: Optional[float] = None

    status: QuoteStatusName
    quality: Optional[QualityStatusName] = None
    tradable: bool

    last: Optional[float] = Field(
        description="Last price — required on the wire, nullable for "
        "OFFLINE; never a fabricated 0"
    )
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    turnover: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    spread: Optional[float] = None

    timestamp: Optional[str] = Field(
        default=None, description="Exchange event time (ISO-8601)"
    )
    received_timestamp: Optional[str] = Field(
        default=None, description="ICYQuant receive time (ISO-8601)"
    )
    quote_age_ms: Optional[int] = None
    latency_ms: Optional[int] = None


class QuoteListResponse(BaseModel):
    items: list[QuoteResponse]
    count: int
    requested: int
    live_count: int
    source: str = Field(description="Adapter that produced the data")


# ── ⑤ / ⑥ / ⑦ Bars ───────────────────────────────────────────────


class BarResponse(BaseModel):
    symbol: str
    exchange: ExchangeName
    timeframe: str
    timestamp: str
    bar_id: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    turnover: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    is_closed: bool = Field(
        description="False while the minute is still accumulating (§7)"
    )
    source: BarSourceName


class BarQualityInfo(BaseModel):
    checked: int
    invalid_count: int
    invalid_bars: list[str]


class MergeInfo(BaseModel):
    """How historical and realtime were joined (§6)."""

    enabled: bool
    historical_count: int
    realtime_count: int
    overlaps: int
    mode: str
    seamless: bool
    historical_last: Optional[str] = None
    realtime_first: Optional[str] = None
    revision_count: int
    revisions: list[dict]
    gap_count: int


class BarSeriesResponse(BaseModel):
    symbol: str
    name: str
    exchange: ExchangeName
    instrument_type: InstrumentTypeName
    timeframe: str
    items: list[BarResponse]
    count: int
    closed_count: int
    has_live: bool
    start: Optional[str] = None
    end: Optional[str] = None
    gaps: list[str]
    quality: BarQualityInfo
    merge: MergeInfo
    source: str


# ── ⑧ Session ────────────────────────────────────────────────────


class NextEventResponse(BaseModel):
    phase: MarketPhaseName
    label: str
    at: str


class SessionResponse(BaseModel):
    exchange: ExchangeName
    market: str
    trading_date: str
    phase: MarketPhaseName
    phase_label: str
    session_start: Optional[str] = Field(
        default=None, description="Segment start, HH:MM:SS"
    )
    session_end: Optional[str] = Field(
        default=None, description="Segment end, HH:MM:SS"
    )
    session_start_at: Optional[str] = Field(
        default=None, description="Segment start, full ISO-8601"
    )
    session_end_at: Optional[str] = None
    is_trading_day: bool
    is_tradable: bool = Field(
        description="The single trade gate for Strategy / Paper Trading"
    )
    next_event: NextEventResponse
    server_time: str
    timezone: str


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    server_time: str


# ── ⑨ Quality ────────────────────────────────────────────────────


class QualityResponse(BaseModel):
    symbol: str
    name: str
    status: QualityStatusName
    tradable: bool
    passed: bool
    action: Optional[GatewayActionName] = None
    checks: dict[str, CheckResult]
    checks_passed: bool
    reasons: list[str]
    quote_age_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    checked_at: Optional[str] = None
    source: str = Field(
        description="Where the verdict came from: "
        "quote_service / quarantine / cache"
    )
    config: dict


class SymbolQualityItem(BaseModel):
    symbol: str
    name: str
    status: QualityRollupStatusName
    tradable: bool
    last: Optional[float] = None
    quote_age_ms: Optional[int] = None
    latency_ms: Optional[int] = None


class QuarantineItem(BaseModel):
    symbol: Optional[str] = None
    status: Optional[str] = None
    reasons: list[str]
    action: Optional[str] = None
    received_at: Optional[str] = None


class QualityOverviewResponse(BaseModel):
    instruments: int
    counts: dict[str, int]
    symbols: list[SymbolQualityItem]
    quarantine_items: list[QuarantineItem]
    config: dict


# ── ⑩ Health ─────────────────────────────────────────────────────


class SymbolCounts(BaseModel):
    total: int
    fresh: int
    warning: int
    stale: int
    invalid: int
    quarantined: int
    offline: int


class FeedInfo(BaseModel):
    started: bool
    running: bool
    adapter: str
    interval_seconds: float
    stats: dict


class HealthSessionInfo(BaseModel):
    phase: MarketPhaseName
    is_tradable: bool


class HealthResponse(BaseModel):
    status: HealthStatusName
    adapter: ComponentStatusName
    redis: ComponentStatusName
    #: The quality *roll-up* uses the health vocabulary (HEALTHY /
    #: DEGRADED / BLOCKED / OFFLINE), not the component vocabulary.
    quality: HealthStatusName
    symbols: SymbolCounts
    instruments: int
    feed: FeedInfo
    cache: dict
    session: HealthSessionInfo
    timeframes: list[str]
    server_time: str
    checked_at: str


class MarketDataWiringResponse(BaseModel):
    """§15 — proof that Paper Trading and the API share one service."""

    quote_service: str
    bar_service: str
    merge_engine: str
    market_cache: str
    trading_calendar: str
    paper_feed: str
    paper_uses_service: bool


__all__ = [
    "CheckResult",
    "BarResponse",
    "BarSeriesResponse",
    "BarQualityInfo",
    "BarSourceName",
    "ComponentStatusName",
    "ErrorResponse",
    "ExchangeName",
    "FeedInfo",
    "GatewayActionName",
    "HealthResponse",
    "HealthSessionInfo",
    "HealthStatusName",
    "InstrumentFilters",
    "InstrumentListResponse",
    "InstrumentResponse",
    "InstrumentTypeName",
    "MarketDataWiringResponse",
    "MarketPhaseName",
    "MergeInfo",
    "NextEventResponse",
    "QualityOverviewResponse",
    "QualityResponse",
    "QualityStatusName",
    "QuarantineItem",
    "QuoteListResponse",
    "QuoteResponse",
    "QuoteStatusName",
    "SessionListResponse",
    "SessionResponse",
    "SymbolCounts",
    "SymbolQualityItem",
    "TradingStatusName",
]
