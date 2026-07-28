"""Market Regime Model – define market states and regime transitions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Regime state definitions
# ------------------------------------------------------------------

class RegimeState:
    """Enumeration of market regime states."""

    # Trend regimes
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    SIDEWAYS = "SIDEWAYS"

    # Volatility regimes
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRISIS = "CRISIS"

    # Macro regimes
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    FLIGHT_TO_QUALITY = "FLIGHT_TO_QUALITY"

    # Composite regimes
    BULL_LOW_VOL = "BULL_LOW_VOL"
    BULL_HIGH_VOL = "BULL_HIGH_VOL"
    BEAR_LOW_VOL = "BEAR_LOW_VOL"
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"
    SIDEWAYS_LOW_VOL = "SIDEWAYS_LOW_VOL"
    SIDEWAYS_HIGH_VOL = "SIDEWAYS_HIGH_VOL"

    @classmethod
    def all_states(cls) -> List[str]:
        return [v for k, v in vars(cls).items()
                if not k.startswith("_") and isinstance(v, str)]

    @classmethod
    def trend_states(cls) -> List[str]:
        return [cls.BULL_TREND, cls.BEAR_TREND, cls.SIDEWAYS]

    @classmethod
    def volatility_states(cls) -> List[str]:
        return [cls.LOW_VOLATILITY, cls.NORMAL_VOLATILITY,
                cls.HIGH_VOLATILITY, cls.CRISIS]

    @classmethod
    def macro_states(cls) -> List[str]:
        return [cls.RISK_ON, cls.RISK_OFF, cls.FLIGHT_TO_QUALITY]


# ------------------------------------------------------------------
# Market Regime
# ------------------------------------------------------------------

@dataclass
class MarketRegime:
    """Complete market regime classification result.

    A MarketRegime captures the current market state along with confidence,
    supporting evidence, and transition signals. This is the central model
    that drives adaptive strategy selection and portfolio allocation.
    """

    state: str  # primary regime state (e.g., "BULL_TREND")

    # Confidence
    confidence: float = 0.0  # 0.0 - 1.0
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)

    # Timestamp
    timestamp: Optional[datetime] = None
    period: str = "1d"  # "1h", "1d", "1w"

    # Sub-signals
    trend_signal: str = ""
    trend_strength: float = 0.0
    volatility_signal: str = ""
    volatility_level: float = 0.0
    macro_signal: str = ""

    # Evidence & features
    features: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)

    # Transition
    previous_state: str = ""
    transition_alert: bool = False
    transition_probability: float = 0.0

    # Strategy guidance
    recommended_strategies: List[str] = field(default_factory=list)
    suggested_exposure: float = 1.0  # 0.0 - 1.0 suggested equity exposure

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_bull(self) -> bool:
        return "BULL" in self.state

    @property
    def is_bear(self) -> bool:
        return "BEAR" in self.state

    @property
    def is_sideways(self) -> bool:
        return "SIDEWAYS" in self.state

    @property
    def is_high_volatility(self) -> bool:
        return "HIGH_VOL" in self.state or self.state == RegimeState.CRISIS

    @property
    def is_low_volatility(self) -> bool:
        return "LOW_VOL" in self.state

    @property
    def is_crisis(self) -> bool:
        return self.state == RegimeState.CRISIS

    @property
    def is_risk_on(self) -> bool:
        return self.macro_signal == RegimeState.RISK_ON

    @property
    def is_risk_off(self) -> bool:
        return self.macro_signal in (RegimeState.RISK_OFF, RegimeState.FLIGHT_TO_QUALITY)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "confidence": self.confidence,
            "confidence_breakdown": self.confidence_breakdown,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "period": self.period,
            "trend_signal": self.trend_signal,
            "trend_strength": self.trend_strength,
            "volatility_signal": self.volatility_signal,
            "volatility_level": self.volatility_level,
            "macro_signal": self.macro_signal,
            "features": self.features,
            "evidence": self.evidence,
            "previous_state": self.previous_state,
            "transition_alert": self.transition_alert,
            "transition_probability": self.transition_probability,
            "recommended_strategies": self.recommended_strategies,
            "suggested_exposure": self.suggested_exposure,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def summary(self) -> str:
        """Human-readable regime summary."""
        parts = [
            f"State: {self.state}",
            f"Confidence: {self.confidence:.1%}",
        ]
        if self.trend_signal:
            parts.append(f"Trend: {self.trend_signal} ({self.trend_strength:.2f})")
        if self.volatility_signal:
            parts.append(f"Vol: {self.volatility_signal} ({self.volatility_level:.2f})")
        if self.macro_signal:
            parts.append(f"Macro: {self.macro_signal}")
        if self.transition_alert:
            parts.append(f"⚠ Transition: {self.transition_probability:.1%}")
        return " | ".join(parts)


# ------------------------------------------------------------------
# Regime Transition Record
# ------------------------------------------------------------------

@dataclass
class RegimeTransition:
    """Record of a regime state transition."""

    from_state: str
    to_state: str
    timestamp: Optional[datetime] = None
    confidence: float = 0.0
    trigger_factors: List[str] = field(default_factory=list)
    duration_in_previous: float = 0.0  # days in previous regime

    def to_dict(self) -> dict:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "confidence": self.confidence,
            "trigger_factors": self.trigger_factors,
            "duration_in_previous": self.duration_in_previous,
        }
