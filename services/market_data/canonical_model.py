"""
Canonical Market Data Model — the single unified data representation
used throughout ICYQuant.

All market data from any exchange, protocol, or asset class is normalized
into these canonical types before reaching downstream consumers.

Commit 16 Part 1.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


# ──────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    FUTURES = "futures"
    OPTION = "option"
    FX = "fx"
    CRYPTO = "crypto"
    INDEX = "index"
    BOND = "bond"
    COMMODITY = "commodity"
    CFD = "cfd"
    WARRANT = "warrant"
    OTHER = "other"


class MarketDataEventType(str, Enum):
    TICK = "tick"
    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "order_book"
    KLINE = "kline"
    OPTION_CHAIN = "option_chain"
    FUTURES = "futures"
    FX = "fx"
    CRYPTO = "crypto"
    INDEX = "index"
    CORPORATE_ACTION = "corporate_action"
    INSTRUMENT = "instrument"
    STATUS = "status"
    UNKNOWN = "unknown"


class DataQuality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    SUSPECT = "suspect"
    POOR = "poor"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# ──────────────────────────────────────────────
#  Core canonical types
# ──────────────────────────────────────────────


@dataclass
class CanonicalMarketData:
    """Base canonical market data object — all events extend this."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: MarketDataEventType = MarketDataEventType.UNKNOWN
    asset_class: AssetClass = AssetClass.OTHER

    # Instrument identity
    instrument_id: str = ""
    canonical_symbol: str = ""
    exchange_id: str = ""
    exchange_code: str = ""
    original_symbol: str = ""

    # Timestamps (all in UTC epoch nanoseconds)
    event_timestamp_ns: int = 0
    exchange_timestamp_ns: int = 0
    received_timestamp_ns: int = 0
    normalized_timestamp_ns: int = 0

    # Quality
    quality: DataQuality = DataQuality.UNKNOWN
    quality_score: float = 0.0
    quality_flags: list[str] = field(default_factory=list)

    # Source tracing
    source_feed: str = ""
    source_protocol: str = ""
    source_raw: Optional[dict[str, Any]] = None
    normalization_version: str = "1.2"

    # Arbitrary extension
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.event_timestamp_ns / 1e9, tz=timezone.utc)

    @property
    def exchange_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.exchange_timestamp_ns / 1e9, tz=timezone.utc)

    def to_summary(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "instrument_id": self.instrument_id,
            "exchange_id": self.exchange_id,
            "canonical_symbol": self.canonical_symbol,
            "quality": self.quality.value,
            "quality_score": self.quality_score,
        }


# ──────────────────────────────────────────────
#  Asset-class-specific canonical types
# ──────────────────────────────────────────────


@dataclass
class CanonicalTick(CanonicalMarketData):
    """Canonical tick — the finest granularity price update."""

    event_type: MarketDataEventType = MarketDataEventType.TICK

    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    last: Decimal = Decimal("0")
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")
    last_size: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    turnover: Decimal = Decimal("0")
    open_interest: Decimal = Decimal("0")

    # Derived
    spread: Decimal = Decimal("0")
    mid: Decimal = Decimal("0")

    # Tick metadata
    tick_direction: str = ""  # up, down, unchanged
    tick_sequence: int = 0
    condition_codes: list[str] = field(default_factory=list)


@dataclass
class CanonicalTrade(CanonicalMarketData):
    """Canonical trade — executed transaction."""

    event_type: MarketDataEventType = MarketDataEventType.TRADE

    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    trade_id: str = ""
    trade_side: str = ""  # buy, sell, unknown
    trade_type: str = ""  # normal, block, auction, off-exchange
    is_reported: bool = False
    accumulated_volume: Decimal = Decimal("0")
    vwap: Decimal = Decimal("0")

    # Counterparty (if available)
    buyer_id: str = ""
    seller_id: str = ""


@dataclass
class CanonicalQuote(CanonicalMarketData):
    """Canonical quote — best bid/ask snapshot."""

    event_type: MarketDataEventType = MarketDataEventType.QUOTE

    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")
    bid_exchange: str = ""
    ask_exchange: str = ""
    quote_condition: str = ""

    spread: Decimal = Decimal("0")
    mid: Decimal = Decimal("0")


@dataclass
class CanonicalOrderBook(CanonicalMarketData):
    """Canonical order book — full depth-of-market snapshot."""

    event_type: MarketDataEventType = MarketDataEventType.ORDER_BOOK

    bids: list[tuple[Decimal, Decimal]] = field(default_factory=list)  # (price, qty)
    asks: list[tuple[Decimal, Decimal]] = field(default_factory=list)  # (price, qty)
    best_bid: Decimal = Decimal("0")
    best_ask: Decimal = Decimal("0")
    best_bid_size: Decimal = Decimal("0")
    best_ask_size: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    mid: Decimal = Decimal("0")

    # Depth aggregation
    depth_levels: int = 0
    is_snapshot: bool = True
    update_type: str = ""  # snapshot, update, clear
    sequence_number: int = 0
    previous_sequence: int = 0


@dataclass
class CanonicalKLine(CanonicalMarketData):
    """Canonical K-line / candlestick bar."""

    event_type: MarketDataEventType = MarketDataEventType.KLINE

    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    close: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    turnover: Decimal = Decimal("0")

    # Bar metadata
    interval: str = ""  # 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M
    bar_open_timestamp_ns: int = 0
    bar_close_timestamp_ns: int = 0
    number_of_trades: int = 0
    taker_buy_volume: Decimal = Decimal("0")
    taker_buy_turnover: Decimal = Decimal("0")

    # Derived
    is_closed: bool = True
    change: Decimal = Decimal("0")
    change_pct: Decimal = Decimal("0")


@dataclass
class CanonicalOptionChain(CanonicalMarketData):
    """Canonical option chain — options series for an underlying."""

    event_type: MarketDataEventType = MarketDataEventType.OPTION_CHAIN
    asset_class: AssetClass = AssetClass.OPTION

    underlying_instrument_id: str = ""
    underlying_price: Decimal = Decimal("0")
    expiration_date: str = ""  # ISO 8601
    strike_price: Decimal = Decimal("0")
    option_type: str = ""  # call / put
    option_style: str = ""  # american / european

    # Greeks
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    implied_volatility: Optional[float] = None

    # Market
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    last: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    open_interest: Decimal = Decimal("0")


@dataclass
class CanonicalFutures(CanonicalMarketData):
    """Canonical futures contract data."""

    event_type: MarketDataEventType = MarketDataEventType.FUTURES
    asset_class: AssetClass = AssetClass.FUTURES

    last: Decimal = Decimal("0")
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    turnover: Decimal = Decimal("0")
    open_interest: Decimal = Decimal("0")
    settlement_price: Decimal = Decimal("0")
    mark_price: Decimal = Decimal("0")
    funding_rate: Decimal = Decimal("0")

    # Contract details
    contract_code: str = ""
    expiry_date: str = ""
    contract_type: str = ""  # perpetual, quarterly, delivery
    multiplier: Decimal = Decimal("1")
    tick_size: Decimal = Decimal("0")


@dataclass
class CanonicalFX(CanonicalMarketData):
    """Canonical FX / forex quote."""

    event_type: MarketDataEventType = MarketDataEventType.FX
    asset_class: AssetClass = AssetClass.FX

    base_currency: str = ""
    quote_currency: str = ""
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    mid: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    spread_pips: float = 0.0
    swap_points: Optional[Decimal] = None

    # Market conditions
    is_indicator: bool = False
    is_fixing: bool = False
    tenor: str = ""  # spot, 1w, 1m, 3m, 6m, 1y


@dataclass
class CanonicalCrypto(CanonicalMarketData):
    """Canonical cryptocurrency market data."""

    event_type: MarketDataEventType = MarketDataEventType.CRYPTO
    asset_class: AssetClass = AssetClass.CRYPTO

    base_asset: str = ""
    quote_asset: str = ""
    last: Decimal = Decimal("0")
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    turnover: Decimal = Decimal("0")
    high_24h: Decimal = Decimal("0")
    low_24h: Decimal = Decimal("0")
    change_24h: Decimal = Decimal("0")
    change_pct_24h: Decimal = Decimal("0")

    # Exchange-specific
    exchange_product_code: str = ""
    is_margin_enabled: bool = False
    is_spot: bool = True


@dataclass
class CanonicalIndex(CanonicalMarketData):
    """Canonical market index value."""

    event_type: MarketDataEventType = MarketDataEventType.INDEX
    asset_class: AssetClass = AssetClass.INDEX

    index_value: Decimal = Decimal("0")
    change: Decimal = Decimal("0")
    change_pct: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    open: Decimal = Decimal("0")
    previous_close: Decimal = Decimal("0")

    # Composition
    constituent_count: int = 0
    divisor: Optional[Decimal] = None
