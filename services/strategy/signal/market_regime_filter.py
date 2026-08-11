"""
Market Regime Filter — Detects market regime and filters signals accordingly.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Supports:
    - Bull / Bear / Range / High Volatility / Low Volatility detection
    - Per-regime alpha enable/disable rules
    - Regime transition detection with hysteresis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.strategy.signal.signal_engine import Signal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULL = "BULL"
    BEAR = "BEAR"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class RegimeConfig:
    """Configuration for a specific market regime."""
    regime: MarketRegime
    enabled_alphas: Set[str] = field(default_factory=set)
    disabled_alphas: Set[str] = field(default_factory=set)
    signal_multiplier: float = 1.0  # Reduce/increase signal strength in this regime
    min_confidence: float = 0.0


@dataclass
class RegimeDetection:
    """Result of market regime detection."""
    current_regime: MarketRegime = MarketRegime.UNKNOWN
    previous_regime: MarketRegime = MarketRegime.UNKNOWN
    confidence: float = 0.0
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    indicators: Dict[str, float] = field(default_factory=dict)
    regime_changed: bool = False


# ---------------------------------------------------------------------------
# Market Regime Filter
# ---------------------------------------------------------------------------

class MarketRegimeFilter:
    """Detects market regime and filters alpha/signal outputs.

    Different alphas perform better in different regimes. This filter:
        1. Detects the current market regime
        2. Enables/disables alphas based on regime rules
        3. Adjusts signal confidence based on regime alignment
    """

    def __init__(self):
        self._current_regime = MarketRegime.UNKNOWN
        self._previous_regime = MarketRegime.UNKNOWN
        self._detection_history: List[RegimeDetection] = []

        # Regime-specific configurations
        self._regime_configs: Dict[MarketRegime, RegimeConfig] = {
            MarketRegime.BULL: RegimeConfig(
                regime=MarketRegime.BULL,
                enabled_alphas={"momentum_alpha", "quality_alpha"},
                signal_multiplier=1.0,
            ),
            MarketRegime.BEAR: RegimeConfig(
                regime=MarketRegime.BEAR,
                enabled_alphas={"value_alpha", "volatility_alpha"},
                disabled_alphas={"momentum_alpha"},
                signal_multiplier=0.8,
            ),
            MarketRegime.RANGE: RegimeConfig(
                regime=MarketRegime.RANGE,
                enabled_alphas={"value_alpha"},
                disabled_alphas={"momentum_alpha", "volatility_alpha"},
                signal_multiplier=0.6,
            ),
            MarketRegime.HIGH_VOLATILITY: RegimeConfig(
                regime=MarketRegime.HIGH_VOLATILITY,
                enabled_alphas={"volatility_alpha"},
                signal_multiplier=0.7,
                min_confidence=0.3,
            ),
            MarketRegime.LOW_VOLATILITY: RegimeConfig(
                regime=MarketRegime.LOW_VOLATILITY,
                enabled_alphas={"momentum_alpha", "value_alpha", "quality_alpha"},
                signal_multiplier=1.0,
            ),
        }

    # ------------------------------------------------------------------
    # Regime Detection
    # ------------------------------------------------------------------

    async def detect_regime(self, market_data: Dict[str, Any]) -> RegimeDetection:
        """Detect the current market regime from market data indicators.

        Args:
            market_data: Dictionary with market indicators like:
                - trend_strength: float
                - volatility: float
                - volume_ratio: float
                - breadth: float
                - vix_level: float

        Returns:
            RegimeDetection with the classified regime.
        """
        # Extract indicators
        trend = market_data.get("trend_strength", 0.0)
        volatility = market_data.get("volatility", 0.5)
        vol_percentile = market_data.get("volatility_percentile", 0.5)

        # Classification logic
        if vol_percentile > 0.8:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(vol_percentile, 0.95)
        elif vol_percentile < 0.2:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 1.0 - max(vol_percentile, 0.05)
        elif trend > 0.3:
            regime = MarketRegime.BULL
            confidence = min(abs(trend), 0.9)
        elif trend < -0.3:
            regime = MarketRegime.BEAR
            confidence = min(abs(trend), 0.9)
        else:
            regime = MarketRegime.RANGE
            confidence = 1.0 - abs(trend)

        # Check for transition
        regime_changed = regime != self._current_regime
        if regime_changed:
            self._previous_regime = self._current_regime
            self._current_regime = regime

        detection = RegimeDetection(
            current_regime=regime,
            previous_regime=self._previous_regime if regime_changed else self._current_regime,
            confidence=confidence,
            indicators={
                "trend_strength": trend,
                "volatility": volatility,
                "volatility_percentile": vol_percentile,
            },
            regime_changed=regime_changed,
        )

        self._detection_history.append(detection)
        if len(self._detection_history) > 1000:
            self._detection_history = self._detection_history[-500:]

        if regime_changed:
            logger.info("Market regime changed: %s → %s (confidence=%.2f)",
                         detection.previous_regime.value, regime.value, confidence)

        return detection

    async def update_regime(self, regime: MarketRegime, confidence: float = 1.0) -> None:
        """Manually set the current market regime."""
        if regime != self._current_regime:
            self._previous_regime = self._current_regime
            self._current_regime = regime
            self._detection_history.append(RegimeDetection(
                current_regime=regime,
                previous_regime=self._previous_regime,
                confidence=confidence,
                regime_changed=True,
            ))

    # ------------------------------------------------------------------
    # Alpha Filtering
    # ------------------------------------------------------------------

    def is_alpha_enabled(self, alpha_id: str) -> bool:
        """Check if an alpha should be active in the current regime."""
        config = self._regime_configs.get(self._current_regime)
        if not config:
            return True

        # Explicitly disabled takes priority
        if alpha_id in config.disabled_alphas:
            return False

        # If there are enabled_alphas, only those are allowed
        if config.enabled_alphas:
            return alpha_id in config.enabled_alphas

        # No restrictions
        return True

    def get_enabled_alphas(self, alpha_ids: List[str]) -> List[str]:
        """Filter a list of alpha IDs to only those enabled in current regime."""
        return [aid for aid in alpha_ids if self.is_alpha_enabled(aid)]

    # ------------------------------------------------------------------
    # Signal Filtering
    # ------------------------------------------------------------------

    def adjust_signal(self, signal: Signal) -> Signal:
        """Adjust signal confidence based on current market regime.

        Returns the signal (modified in-place) with adjusted confidence.
        """
        config = self._regime_configs.get(self._current_regime)
        if not config:
            signal.market_regime = self._current_regime.value
            return signal

        # Apply signal multiplier
        signal.confidence *= config.signal_multiplier

        # Apply minimum confidence threshold
        signal.confidence = max(signal.confidence, config.min_confidence)

        # Record regime
        signal.market_regime = self._current_regime.value

        return signal

    def should_filter(self, signal: Signal) -> bool:
        """Check if a signal should be filtered out in the current regime."""
        config = self._regime_configs.get(self._current_regime)
        if not config:
            return False

        # Check alpha-level filtering
        for alpha_id in signal.alpha_scores:
            if not self.is_alpha_enabled(alpha_id):
                return True

        return False

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_regime_config(self, regime: MarketRegime, config: RegimeConfig) -> None:
        """Configure rules for a specific market regime."""
        self._regime_configs[regime] = config

    def get_regime_config(self, regime: MarketRegime) -> Optional[RegimeConfig]:
        return self._regime_configs.get(regime)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def current_regime(self) -> MarketRegime:
        return self._current_regime

    def get_recent_detections(self, limit: int = 10) -> List[RegimeDetection]:
        return self._detection_history[-limit:]

    def regime_stability(self, window: int = 10) -> float:
        """How stable has the regime been? 1.0 = no changes in window."""
        recent = self._detection_history[-window:]
        if len(recent) < 2:
            return 1.0
        changes = sum(1 for d in recent if d.regime_changed)
        return 1.0 - (changes / len(recent))
