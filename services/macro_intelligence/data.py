"""Macro Data Model.

Defines the core data structures for macro intelligence analysis,
including economic indicators, central bank data, and macro events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class IndicatorCategory(str, Enum):
    """Category of macroeconomic indicator."""
    GROWTH = "growth"           # GDP, PMI, industrial production
    EMPLOYMENT = "employment"   # NFP, unemployment rate, wage growth
    INFLATION = "inflation"     # CPI, PPI, PCE
    MONETARY = "monetary"       # interest rate, M2, balance sheet
    TRADE = "trade"             # trade balance, current account
    HOUSING = "housing"         # housing starts, home prices
    CONSUMER = "consumer"       # retail sales, consumer confidence
    SENTIMENT = "sentiment"     # business confidence, sentiment indices


class IndicatorDirection(str, Enum):
    """Direction of indicator impact on markets."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class MacroIndicator:
    """A single macroeconomic data point.

    Attributes:
        name: Indicator name (e.g. "CPI", "GDP", "NFP").
        value: Current value.
        category: Category of the indicator.
        unit: Measurement unit (e.g. "%", "USD", "index").
        frequency: Release frequency ("monthly", "quarterly", "daily").
        timestamp: Observation timestamp.
        previous: Previous value for comparison.
        expected: Market consensus expectation.
        direction: Market impact direction when rising.
        source: Data source name.
    """
    name: str
    value: float
    category: IndicatorCategory
    unit: str = ""
    frequency: str = "monthly"
    timestamp: Optional[datetime] = None
    previous: Optional[float] = None
    expected: Optional[float] = None
    direction: IndicatorDirection = IndicatorDirection.NEUTRAL
    source: str = ""

    @property
    def change(self) -> Optional[float]:
        """Change from previous value."""
        if self.previous is not None:
            return self.value - self.previous
        return None

    @property
    def change_pct(self) -> Optional[float]:
        """Percentage change from previous value."""
        if self.previous is not None and self.previous != 0:
            return (self.value - self.previous) / abs(self.previous) * 100
        return None

    @property
    def surprise(self) -> Optional[float]:
        """Deviation from market expectation."""
        if self.expected is not None:
            return self.value - self.expected
        return None

    @property
    def is_improving(self) -> bool:
        """Whether the indicator is improving (positive change for positive direction)."""
        if self.change is None:
            return False
        if self.direction == IndicatorDirection.POSITIVE:
            return self.change > 0
        elif self.direction == IndicatorDirection.NEGATIVE:
            return self.change < 0
        return False


@dataclass
class MacroDataSnapshot:
    """A snapshot of macro data at a point in time.

    Contains a collection of MacroIndicator values representing
    the current macro environment.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    indicators: list[MacroIndicator] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> Optional[MacroIndicator]:
        """Get an indicator by name."""
        for ind in self.indicators:
            if ind.name == name:
                return ind
        return None

    def get_by_category(self, category: IndicatorCategory) -> list[MacroIndicator]:
        """Get all indicators in a category."""
        return [ind for ind in self.indicators if ind.category == category]

    def add(self, indicator: MacroIndicator) -> None:
        """Add an indicator to the snapshot."""
        self.indicators.append(indicator)

    def __len__(self) -> int:
        return len(self.indicators)

    def __iter__(self):
        return iter(self.indicators)


@dataclass
class CentralBankEvent:
    """A central bank decision or communication event.

    Attributes:
        bank: Central bank identifier (e.g. "FED", "ECB", "BOJ", "PBOC").
        event_type: Type of event ("decision", "minutes", "speech", "report").
        date: Event date.
        rate_change: Basis point change in policy rate.
        current_rate: Current policy rate as percentage.
        statement_text: Policy statement text (if available).
        sentiment: Extracted sentiment ("hawkish", "dovish", "neutral").
        confidence: Sentiment classification confidence (0-1).
        key_phrases: Extracted key phrases from statement.
    """
    bank: str
    event_type: str
    date: datetime
    rate_change: float = 0.0
    current_rate: float = 0.0
    statement_text: str = ""
    sentiment: str = "neutral"
    confidence: float = 0.5
    key_phrases: list[str] = field(default_factory=list)


@dataclass
class MacroEvent:
    """A scheduled or unscheduled macro event.

    Attributes:
        name: Event name (e.g. "FOMC Meeting", "CPI Release").
        event_type: Type ("data_release", "policy_meeting", "speech", "geopolitical").
        scheduled_time: Expected event time.
        country: Affected country/region.
        importance: Event importance (1-5 scale).
        assets_affected: List of affected asset classes.
        historical_impact: Historical average impact on key assets.
    """
    name: str
    event_type: str
    scheduled_time: Optional[datetime] = None
    country: str = "US"
    importance: int = 3
    assets_affected: list[str] = field(default_factory=list)
    historical_impact: dict[str, float] = field(default_factory=dict)


class MacroRegimeState(str, Enum):
    """Composite macro regime states."""
    GOLDILOCKS = "goldilocks"           # growth ↑, inflation ↓
    REFLATION = "reflation"             # growth ↑, inflation ↑ (early)
    OVERHEATING = "overheating"         # growth →, inflation ↑↑
    STAGFLATION = "stagflation"         # growth ↓, inflation ↑
    RECESSION = "recession"             # growth ↓, inflation ↓
    RECOVERY = "recovery"               # growth ↑ from low base
    TIGHTENING = "tightening"           # hawkish policy
    EASING = "easing"                   # dovish policy
    LIQUIDITY_CRUNCH = "liquidity_crunch"  # credit tightening
    LIQUIDITY_SURGE = "liquidity_surge"    # abundant liquidity


@dataclass
class MacroRegime:
    """The classified macro regime result.

    Attributes:
        state: The macro regime state.
        confidence: Classification confidence (0-1).
        growth_score: Growth dimension score (-1 to 1).
        inflation_score: Inflation dimension score (-1 to 1).
        liquidity_score: Liquidity dimension score (-1 to 1).
        policy_score: Policy stance score (-1 to 1, negative = hawkish).
        timestamp: Classification timestamp.
        details: Additional regime details and component scores.
    """
    state: MacroRegimeState
    confidence: float
    growth_score: float = 0.0
    inflation_score: float = 0.0
    liquidity_score: float = 0.0
    policy_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_risk_on(self) -> bool:
        """Whether regime is favorable for risk assets."""
        return self.state in (
            MacroRegimeState.GOLDILOCKS,
            MacroRegimeState.REFLATION,
            MacroRegimeState.RECOVERY,
            MacroRegimeState.EASING,
            MacroRegimeState.LIQUIDITY_SURGE,
        )

    @property
    def is_risk_off(self) -> bool:
        """Whether regime is unfavorable for risk assets."""
        return self.state in (
            MacroRegimeState.STAGFLATION,
            MacroRegimeState.RECESSION,
            MacroRegimeState.LIQUIDITY_CRUNCH,
            MacroRegimeState.TIGHTENING,
        )

    @property
    def summary(self) -> str:
        return f"{self.state.value} (confidence: {self.confidence:.0%})"


__all__ = [
    "IndicatorCategory",
    "IndicatorDirection",
    "MacroIndicator",
    "MacroDataSnapshot",
    "CentralBankEvent",
    "MacroEvent",
    "MacroRegimeState",
    "MacroRegime",
]
