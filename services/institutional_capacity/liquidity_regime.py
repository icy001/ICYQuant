"""
Liquidity Regime — Classifies market into liquidity regimes.

Regimes: NORMAL, HIGH_LIQUIDITY, LOW_LIQUIDITY, STRESSED, CRISIS

Recognizes that liquidity is not static and adjusts capacity expectations accordingly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityRegime(str, Enum):
    HIGH_LIQUIDITY = "high_liquidity"
    NORMAL = "normal"
    LOW_LIQUIDITY = "low_liquidity"
    STRESSED = "stressed"
    CRISIS = "crisis"


@dataclass
class RegimeCharacteristics:
    """Characteristics of a liquidity regime."""

    regime: LiquidityRegime
    volume_multiplier: float = 1.0
    spread_multiplier: float = 1.0
    depth_multiplier: float = 1.0
    participation_cap: float = 0.10
    execution_throttle: float = 1.0
    description: str = ""


REGIME_PROFILES: Dict[LiquidityRegime, RegimeCharacteristics] = {
    LiquidityRegime.HIGH_LIQUIDITY: RegimeCharacteristics(
        regime=LiquidityRegime.HIGH_LIQUIDITY,
        volume_multiplier=1.3, spread_multiplier=0.7,
        depth_multiplier=1.2, participation_cap=0.12,
        execution_throttle=1.2, description="Above-average liquidity",
    ),
    LiquidityRegime.NORMAL: RegimeCharacteristics(
        regime=LiquidityRegime.NORMAL,
        volume_multiplier=1.0, spread_multiplier=1.0,
        depth_multiplier=1.0, participation_cap=0.10,
        execution_throttle=1.0, description="Normal market conditions",
    ),
    LiquidityRegime.LOW_LIQUIDITY: RegimeCharacteristics(
        regime=LiquidityRegime.LOW_LIQUIDITY,
        volume_multiplier=0.7, spread_multiplier=1.5,
        depth_multiplier=0.6, participation_cap=0.06,
        execution_throttle=0.7, description="Below-average liquidity",
    ),
    LiquidityRegime.STRESSED: RegimeCharacteristics(
        regime=LiquidityRegime.STRESSED,
        volume_multiplier=0.4, spread_multiplier=3.0,
        depth_multiplier=0.3, participation_cap=0.03,
        execution_throttle=0.4, description="Market under stress",
    ),
    LiquidityRegime.CRISIS: RegimeCharacteristics(
        regime=LiquidityRegime.CRISIS,
        volume_multiplier=0.15, spread_multiplier=6.0,
        depth_multiplier=0.1, participation_cap=0.01,
        execution_throttle=0.15, description="Liquidity crisis",
    ),
}


@dataclass
class RegimeTransition:
    """A liquidity regime transition event."""

    from_regime: LiquidityRegime
    to_regime: LiquidityRegime
    timestamp: str
    trigger: str = ""
    confidence: float = 1.0


class LiquidityRegimeDetector:
    """Detects and tracks liquidity regime changes."""

    def __init__(self):
        self._current_regime: LiquidityRegime = LiquidityRegime.NORMAL
        self._history: List[RegimeTransition] = []
        self._regime_scores: Dict[LiquidityRegime, float] = {r: 0.0 for r in LiquidityRegime}

    @property
    def current(self) -> LiquidityRegime:
        return self._current_regime

    @property
    def characteristics(self) -> RegimeCharacteristics:
        return REGIME_PROFILES[self._current_regime]

    def assess(
        self,
        volume_change_pct: float = 0.0,
        spread_change_pct: float = 0.0,
        depth_change_pct: float = 0.0,
        volatility_change_pct: float = 0.0,
    ) -> LiquidityRegime:
        """Assess current liquidity regime from market metrics."""
        # Composite stress score
        stress_score = 0.0
        stress_score += max(0, -volume_change_pct) * 0.3
        stress_score += max(0, spread_change_pct) * 0.3
        stress_score += max(0, -depth_change_pct) * 0.2
        stress_score += max(0, volatility_change_pct) * 0.2

        if stress_score > 0.6:
            new_regime = LiquidityRegime.CRISIS
        elif stress_score > 0.35:
            new_regime = LiquidityRegime.STRESSED
        elif stress_score > 0.15:
            new_regime = LiquidityRegime.LOW_LIQUIDITY
        elif stress_score < -0.10:
            new_regime = LiquidityRegime.HIGH_LIQUIDITY
        else:
            new_regime = LiquidityRegime.NORMAL

        if new_regime != self._current_regime:
            self._record_transition(new_regime, f"stress_score={stress_score:.2f}")

        return self._current_regime

    def force_regime(self, regime: LiquidityRegime, reason: str = "manual") -> None:
        self._record_transition(regime, reason)

    def _record_transition(self, to_regime: LiquidityRegime, trigger: str) -> None:
        from_regime = self._current_regime
        self._current_regime = to_regime
        self._history.append(RegimeTransition(
            from_regime=from_regime, to_regime=to_regime,
            timestamp=datetime.now(timezone.utc).isoformat(), trigger=trigger,
        ))

    def recent_transitions(self, n: int = 10) -> List[RegimeTransition]:
        return self._history[-n:]

    def is_stressed(self) -> bool:
        return self._current_regime in (LiquidityRegime.STRESSED, LiquidityRegime.CRISIS)

    def summary(self) -> Dict[str, Any]:
        return {
            "current_regime": self._current_regime.value,
            "is_stressed": self.is_stressed(),
            "participation_cap": self.characteristics.participation_cap,
            "execution_throttle": self.characteristics.execution_throttle,
            "transitions": len(self._history),
        }
