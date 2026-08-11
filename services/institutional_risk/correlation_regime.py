"""CorrelationRegime — detect correlation regime changes.

Markets alternate between low-correlation (diversification works)
and high-correlation (diversification fails) regimes.
This module detects transitions between these regimes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class CorrelationRegime(Enum):
    """Correlation regime types."""

    LOW = auto()       # avg corr < 0.2 — diversification works well
    MODERATE = auto()  # avg corr 0.2-0.5 — normal market
    HIGH = auto()      # avg corr 0.5-0.7 — diversification weakening
    CRISIS = auto()    # avg corr > 0.7 — one big trade
    UNKNOWN = auto()


@dataclass
class RegimeTransition:
    """A detected regime change."""

    timestamp: float
    from_regime: CorrelationRegime
    to_regime: CorrelationRegime
    avg_correlation: float = 0.0
    entities_affected: int = 0


@dataclass
class RegimeResult:
    """Correlation regime analysis result."""

    entity_id: str
    current_regime: CorrelationRegime = CorrelationRegime.UNKNOWN
    avg_correlation: float = 0.0
    vol_of_corr: float = 0.0
    regime_stability: float = 0.0  # how stable is the current regime
    transition_count: int = 0
    transitions: List[RegimeTransition] = field(default_factory=list)
    warning: str = ""


class CorrelationRegimeDetector:
    """Detects correlation regime transitions.

    Usage::

        detector = CorrelationRegimeDetector()
        result = detector.analyze("portfolio_1", pairwise_correlations)
        if result.current_regime == CorrelationRegime.CRISIS:
            print("CRISIS: One Big Trade mode")
    """

    def __init__(
        self,
        low_threshold: float = 0.20,
        high_threshold: float = 0.50,
        crisis_threshold: float = 0.70,
        transition_confirmations: int = 3,
    ):
        self._low_threshold = low_threshold
        self._high_threshold = high_threshold
        self._crisis_threshold = crisis_threshold
        self._transition_confirmations = transition_confirmations
        self._current_regime: CorrelationRegime = CorrelationRegime.UNKNOWN
        self._regime_history: List[Tuple[float, CorrelationRegime, float]] = []
        self._transitions: List[RegimeTransition] = []

    def classify(self, avg_correlation: float) -> CorrelationRegime:
        """Classify a correlation value into a regime."""
        if avg_correlation >= self._crisis_threshold:
            return CorrelationRegime.CRISIS
        if avg_correlation >= self._high_threshold:
            return CorrelationRegime.HIGH
        if avg_correlation >= self._low_threshold:
            return CorrelationRegime.MODERATE
        return CorrelationRegime.LOW

    def update(
        self,
        entity_id: str,
        avg_correlation: float,
        timestamp: Optional[float] = None,
    ) -> RegimeResult:
        """Update with a new correlation observation.

        Args:
            entity_id: portfolio or capital pool id
            avg_correlation: current average pairwise correlation
            timestamp: observation timestamp
        """
        import time
        ts = timestamp or time.time()

        new_regime = self.classify(avg_correlation)

        # record
        self._regime_history.append((ts, new_regime, avg_correlation))
        if len(self._regime_history) > 1000:
            self._regime_history = self._regime_history[-1000:]

        # detect transition (need N confirmations)
        if new_regime != self._current_regime:
            recent = self._regime_history[-self._transition_confirmations:]
            same_as_new = sum(1 for _, r, _ in recent if r == new_regime)
            if same_as_new >= self._transition_confirmations:
                transition = RegimeTransition(
                    timestamp=ts,
                    from_regime=self._current_regime,
                    to_regime=new_regime,
                    avg_correlation=avg_correlation,
                    entities_affected=0,
                )
                self._transitions.append(transition)
                self._current_regime = new_regime

        # regime stability: how long since last transition
        stability = 0.0
        if self._transitions:
            stability = (ts - self._transitions[-1].timestamp) / 86400  # days

        # vol of correlation
        vol_corr = 0.0
        if len(self._regime_history) >= 10:
            recent_corrs = [c for _, _, c in self._regime_history[-10:]]
            avg = sum(recent_corrs) / len(recent_corrs)
            vol_corr = math.sqrt(
                sum((c - avg) ** 2 for c in recent_corrs) / len(recent_corrs)
            )

        # warning
        warning = ""
        if self._current_regime == CorrelationRegime.CRISIS:
            warning = "CRISIS REGIME: All correlations elevated — do NOT rely on diversification"
        elif self._current_regime == CorrelationRegime.HIGH:
            warning = "HIGH CORRELATION: Diversification benefits severely diminished"

        return RegimeResult(
            entity_id=entity_id,
            current_regime=self._current_regime,
            avg_correlation=avg_correlation,
            vol_of_corr=vol_corr,
            regime_stability=stability,
            transition_count=len(self._transitions),
            transitions=list(self._transitions[-5:]),
            warning=warning,
        )

    def get_current_regime(self) -> CorrelationRegime:
        """Get current correlation regime."""
        return self._current_regime

    def reset(self) -> None:
        """Reset regime tracking."""
        self._current_regime = CorrelationRegime.UNKNOWN
        self._regime_history.clear()
        self._transitions.clear()
