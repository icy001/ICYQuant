"""Volatility Regime Engine.

Classifies and predicts volatility regimes to guide position sizing,
stop-loss adjustments, and leverage limits across the trading system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VolatilityRegime(str, Enum):
    """Volatility regime classification."""

    LOW_VOL = "low_vol"
    NORMAL_VOL = "normal_vol"
    HIGH_VOL = "high_vol"
    CRISIS_VOL = "crisis_vol"


class RegimeAction(str, Enum):
    """Recommended action per regime."""

    FULL_SIZE = "full_size"
    REDUCED = "reduced"
    DEFENSIVE = "defensive"
    STOP = "stop"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class RegimeResult:
    """Volatility regime classification result.

    Attributes:
        regime: Current volatility regime.
        vix: VIX level.
        vix_percentile: VIX historical percentile.
        term_structure: VIX term structure state.
        recommended_action: Suggested portfolio action.
        max_position_size: Maximum position (fraction).
        max_leverage: Maximum allowed leverage.
        confidence: Classification confidence.
    """

    regime: VolatilityRegime = VolatilityRegime.NORMAL_VOL
    vix: float = 15.0
    vix_percentile: float = 50.0
    term_structure: str = "contango"
    recommended_action: RegimeAction = RegimeAction.FULL_SIZE
    max_position_size: float = 0.25
    max_leverage: float = 2.0
    confidence: float = 0.5

    @property
    def is_stressed(self) -> bool:
        return self.regime in (VolatilityRegime.HIGH_VOL, VolatilityRegime.CRISIS_VOL)

    @property
    def size_multiplier(self) -> float:
        """Position size multiplier for current regime."""
        mapping = {
            VolatilityRegime.LOW_VOL: 1.2,
            VolatilityRegime.NORMAL_VOL: 1.0,
            VolatilityRegime.HIGH_VOL: 0.6,
            VolatilityRegime.CRISIS_VOL: 0.25,
        }
        return mapping.get(self.regime, 1.0)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class VolatilityRegimeEngine:
    """Classifies and predicts volatility regimes.

    Uses VIX level, term structure, and vol-of-vol to determine
    the appropriate trading posture for the current environment.

    Attributes:
        vix_history: Historical VIX readings for percentile calculation.
        REGIME_THRESHOLDS: VIX thresholds per regime.
    """

    REGIME_THRESHOLDS: dict[VolatilityRegime, float] = {
        VolatilityRegime.LOW_VOL: 12.0,
        VolatilityRegime.NORMAL_VOL: 20.0,
        VolatilityRegime.HIGH_VOL: 30.0,
        VolatilityRegime.CRISIS_VOL: 45.0,
    }

    # Regime → portfolio constraints
    REGIME_CONSTRAINTS: dict[VolatilityRegime, dict[str, Any]] = {
        VolatilityRegime.LOW_VOL: {
            "action": RegimeAction.FULL_SIZE,
            "max_position": 0.30,
            "max_leverage": 2.5,
        },
        VolatilityRegime.NORMAL_VOL: {
            "action": RegimeAction.FULL_SIZE,
            "max_position": 0.25,
            "max_leverage": 2.0,
        },
        VolatilityRegime.HIGH_VOL: {
            "action": RegimeAction.REDUCED,
            "max_position": 0.15,
            "max_leverage": 1.0,
        },
        VolatilityRegime.CRISIS_VOL: {
            "action": RegimeAction.STOP,
            "max_position": 0.05,
            "max_leverage": 0.0,
        },
    }

    def __init__(self) -> None:
        self.vix_history: list[float] = []

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, vix: float,
                 vix_term: str = "contango",
                 vol_of_vol: float = 0.0) -> RegimeResult:
        """Classify volatility regime from VIX and related indicators.

        Args:
            vix: Current VIX level.
            vix_term: Futures term structure ('contango'/'backwardation').
            vol_of_vol: Volatility of VIX (VVIX-style).

        Returns:
            RegimeResult with regime and trading constraints.
        """
        self.vix_history.append(vix)
        if len(self.vix_history) > 200:
            self.vix_history[:] = self.vix_history[-200:]

        # Regime classification
        regime = self._classify_regime(vix, vol_of_vol, vix_term)

        # Percentile
        percentile = self._compute_percentile(vix)

        # Constraints
        constraints = self.REGIME_CONSTRAINTS[regime]

        # Confidence
        confidence = self._compute_confidence(vix, len(self.vix_history))

        return RegimeResult(
            regime=regime,
            vix=vix,
            vix_percentile=percentile,
            term_structure=vix_term,
            recommended_action=constraints["action"],
            max_position_size=constraints["max_position"],
            max_leverage=constraints["max_leverage"],
            confidence=confidence,
        )

    def _classify_regime(self, vix: float,
                         vol_of_vol: float,
                         vix_term: str) -> VolatilityRegime:
        """Determine volatility regime from VIX."""
        # Upgrade regime if term structure is in backwardation
        if vix_term == "backwardation" and vix >= 20:
            vix *= 1.15
            if vol_of_vol > 0.3:
                vix *= 1.1

        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.CRISIS_VOL]:
            return VolatilityRegime.CRISIS_VOL
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.HIGH_VOL]:
            return VolatilityRegime.HIGH_VOL
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.NORMAL_VOL]:
            return VolatilityRegime.NORMAL_VOL
        return VolatilityRegime.LOW_VOL

    def _compute_percentile(self, vix: float) -> float:
        """Estimate VIX percentile from history."""
        if len(self.vix_history) < 2:
            return 50.0
        lower = sum(1 for v in self.vix_history if v < vix)
        return round(lower / len(self.vix_history) * 100, 1)

    def _compute_confidence(self, vix: float, history_len: int) -> float:
        confidence = 0.4
        if history_len > 30:
            confidence += 0.15
        if history_len > 60:
            confidence += 0.10
        if vix > 25:
            confidence += 0.10
        if vix < 12:
            confidence += 0.10
        return min(0.95, confidence)

    # ------------------------------------------------------------------
    # Quick scan
    # ------------------------------------------------------------------

    def quick_classify(self, vix: float) -> dict[str, Any]:
        """Fast regime classification from VIX alone."""
        result = self.classify(vix)
        return {
            "regime": result.regime.value,
            "stressed": result.is_stressed,
            "max_leverage": result.max_leverage,
            "max_position": result.max_position_size,
        }

    def clear(self) -> None:
        self.vix_history.clear()
