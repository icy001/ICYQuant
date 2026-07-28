"""Capital Flow Intelligence data models.

Defines core data structures for capital flow analysis including:
- CapitalFlowRecord: raw flow data point
- FlowEvent: significant capital movement event
- SectorRotation: sector-level capital migration
- FlowAlphaSignal: flow-derived alpha factor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FlowSource(str, Enum):
    """Data source for capital flow signals."""

    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    HEDGE_FUND = "hedge_fund"
    INSTITUTIONAL = "institutional"
    OPTIONS = "options"
    DARK_POOL = "dark_pool"
    FOREIGN = "foreign"
    BOND = "bond"
    COMMODITY = "commodity"
    INTERNAL = "internal"


class FlowDirection(str, Enum):
    """Direction of capital movement."""

    STRONG_INFLOW = "strong_inflow"
    INFLOW = "inflow"
    NEUTRAL = "neutral"
    OUTFLOW = "outflow"
    STRONG_OUTFLOW = "strong_outflow"


class FlowAssetClass(str, Enum):
    """Asset class for capital flow classification."""

    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    CRYPTO = "crypto"
    REAL_ESTATE = "real_estate"
    CASH = "cash"
    HYBRID = "hybrid"


class InstitutionalBehavior(str, Enum):
    """Detected institutional behavior pattern."""

    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    HOLDING = "holding"
    ROTATION_IN = "rotation_in"
    ROTATION_OUT = "rotation_out"
    HEDGING = "hedging"
    SPECULATIVE = "speculative"


class SmartMoneyAction(str, Enum):
    """Smart money action classification."""

    ENTRY = "entry"
    EXIT = "exit"
    ADDING = "adding"
    REDUCING = "reducing"
    WAITING = "waiting"


class LiquidityRegime(str, Enum):
    """Liquidity environment classification."""

    ABUNDANT = "abundant"
    EXPANDING = "expanding"
    NEUTRAL = "neutral"
    CONTRACTING = "contracting"
    TIGHT = "tight"
    CRISIS = "crisis"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class CapitalFlowRecord:
    """A single capital flow data point.

    Attributes:
        asset: Asset identifier (ticker, ETF code, sector).
        source: Data source of the flow.
        direction: Direction of capital movement.
        amount: Flow amount (positive=inflow, negative=outflow).
        timestamp: When the flow was recorded.
        asset_class: Asset class category.
        confidence: Reliability of the flow data [0.0, 1.0].
        description: Human-readable description.
        metadata: Additional source-specific metadata.
    """

    asset: str
    source: FlowSource = FlowSource.INSTITUTIONAL
    direction: FlowDirection = FlowDirection.NEUTRAL
    amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    asset_class: FlowAssetClass = FlowAssetClass.EQUITY
    confidence: float = 0.5
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0

    @property
    def is_inflow(self) -> bool:
        return self.direction in (FlowDirection.INFLOW, FlowDirection.STRONG_INFLOW)

    @property
    def is_outflow(self) -> bool:
        return self.direction in (FlowDirection.OUTFLOW, FlowDirection.STRONG_OUTFLOW)

    @property
    def is_strong(self) -> bool:
        return self.direction in (FlowDirection.STRONG_INFLOW, FlowDirection.STRONG_OUTFLOW)

    @property
    def is_significant(self) -> bool:
        return self.confidence >= 0.6 and self.amount != 0.0

    @property
    def net_flow_value(self) -> float:
        multiplier = 1.0 if self.is_inflow else -1.0 if self.is_outflow else 0.0
        return abs(self.amount) * multiplier * self.confidence


@dataclass
class FlowEvent:
    """A significant capital flow event.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of flow event.
        description: Human-readable description.
        assets: Affected assets.
        flow_records: Associated flow records.
        total_amount: Aggregate flow amount.
        timestamp: When the event was detected.
        intensity: Event significance [0.0, 1.0].
        expected_impact: Expected market impact description.
        duration_estimate: Estimated duration in hours.
    """

    event_id: str
    event_type: str
    description: str
    assets: list[str] = field(default_factory=list)
    flow_records: list[CapitalFlowRecord] = field(default_factory=list)
    total_amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    intensity: float = 0.5
    expected_impact: str = "neutral"
    duration_estimate: float = 24.0

    @property
    def is_high_impact(self) -> bool:
        return self.intensity >= 0.7

    @property
    def record_count(self) -> int:
        return len(self.flow_records)


@dataclass
class SectorRotation:
    """Sector-level capital rotation analysis.

    Attributes:
        name: Rotation name / identifier.
        source_sectors: Sectors losing capital.
        target_sectors: Sectors gaining capital.
        strength: Rotation strength [0.0, 1.0].
        confidence: Detection confidence [0.0, 1.0].
        timestamp: Detection time.
        flow_amount: Net capital flow between sectors.
        description: Human-readable description.
        duration: Expected rotation duration in days.
    """

    name: str
    source_sectors: list[str] = field(default_factory=list)
    target_sectors: list[str] = field(default_factory=list)
    strength: float = 0.5
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    flow_amount: float = 0.0
    description: str = ""
    duration: int = 7

    @property
    def is_significant(self) -> bool:
        return self.strength >= 0.4 and self.confidence >= 0.4

    @property
    def target_count(self) -> int:
        return len(self.target_sectors)


@dataclass
class FlowAlphaSignal:
    """Capital flow-derived alpha signal.

    Attributes:
        signal_id: Unique signal identifier.
        asset: Target asset or sector.
        factor_name: Alpha factor name.
        value: Signal value (z-score).
        direction: Expected price direction (1=bullish, -1=bearish, 0=neutral).
        confidence: Signal confidence [0.0, 1.0].
        horizon: Expected signal horizon in days.
        components: Contributing sub-factors and values.
        metadata: Additional context.
    """

    signal_id: str
    asset: str
    factor_name: str
    value: float = 0.0
    direction: int = 0
    confidence: float = 0.5
    horizon: int = 5
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.5 and self.direction != 0

    @property
    def absolute_strength(self) -> float:
        return abs(self.value) * self.confidence
