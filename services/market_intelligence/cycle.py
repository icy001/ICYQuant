from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CyclePhase(str, Enum):
    RECOVERY = "RECOVERY"
    EXPANSION = "EXPANSION"
    PEAK = "PEAK"
    CONTRACTION = "CONTRACTION"
    RECESSION = "RECESSION"


class CycleDuration(str, Enum):
    SHORT_TERM = "SHORT_TERM"  # < 6 months
    MEDIUM_TERM = "MEDIUM_TERM"  # 6-24 months
    LONG_TERM = "LONG_TERM"  # > 24 months


@dataclass
class CycleIndicators:
    leading_index: float  # Composite leading indicator
    coincident_index: float  # Coincident indicator
    lagging_index: float  # Lagging indicator
    capacity_utilization: float
    consumer_confidence: float
    business_sentiment: float
    inventory_to_sales: float


@dataclass
class CycleAnalysis:
    phase: CyclePhase
    confidence: float
    duration_category: CycleDuration
    months_in_phase: int
    next_phase_probability: Dict[CyclePhase, float] = field(default_factory=dict)
    sector_implications: Dict[str, str] = field(default_factory=dict)


class EconomicCycleEngine:
    """Economic Cycle Engine - identifies and analyzes economic cycle phases."""

    def __init__(self):
        self.history: List[CyclePhase] = []

    def analyze(self, economy):
        """Analyze the current economic cycle phase.

        Args:
            economy: Economic data - can be CycleIndicators dataclass or dict/symbol.

        Returns:
            Dict containing cycle analysis result.
        """
        if isinstance(economy, CycleIndicators):
            return self._analyze_cycle(economy)
        return {"cycle": economy}

    def _analyze_cycle(self, indicators: CycleIndicators) -> dict:
        phase = self._determine_phase(indicators)
        confidence = self._calculate_confidence(indicators)
        duration = self._estimate_duration(indicators)
        next_phase = self._predict_next_phase(phase, indicators)
        sector_implications = self._sector_implications(phase)

        self.history.append(phase)

        return {
            "cycle": {
                "phase": phase.value,
                "confidence": round(confidence, 2),
                "duration_category": duration.value,
                "leading_index": round(indicators.leading_index, 2),
                "coincident_index": round(indicators.coincident_index, 2),
                "consumer_confidence": round(indicators.consumer_confidence, 2),
                "capacity_utilization": round(indicators.capacity_utilization, 2),
                "next_phase_probability": {k.value: round(v, 2) for k, v in next_phase.items()},
                "sector_implications": sector_implications,
            }
        }

    def _determine_phase(self, indicators: CycleIndicators) -> CyclePhase:
        if indicators.leading_index < -0.02 and indicators.coincident_index < -0.01:
            return CyclePhase.RECESSION
        elif indicators.leading_index > 0.02 and indicators.coincident_index > 0.01:
            if indicators.capacity_utilization > 0.85:
                return CyclePhase.PEAK
            return CyclePhase.EXPANSION
        elif indicators.leading_index > 0 and indicators.coincident_index < 0:
            return CyclePhase.RECOVERY
        return CyclePhase.CONTRACTION

    def _calculate_confidence(self, indicators: CycleIndicators) -> float:
        base = 0.5
        if abs(indicators.leading_index) > 0.03:
            base += 0.15
        if abs(indicators.coincident_index) > 0.02:
            base += 0.15
        if indicators.consumer_confidence > 80 or indicators.consumer_confidence < 40:
            base += 0.10
        if indicators.capacity_utilization > 0.8 or indicators.capacity_utilization < 0.6:
            base += 0.10
        return min(1.0, base)

    def _estimate_duration(self, indicators: CycleIndicators) -> CycleDuration:
        if abs(indicators.leading_index) > 0.03:
            return CycleDuration.SHORT_TERM
        elif abs(indicators.leading_index) > 0.01:
            return CycleDuration.MEDIUM_TERM
        return CycleDuration.LONG_TERM

    def _predict_next_phase(self, current: CyclePhase, indicators: CycleIndicators) -> Dict[CyclePhase, float]:
        transitions = {
            CyclePhase.RECOVERY: {CyclePhase.EXPANSION: 0.6, CyclePhase.RECOVERY: 0.3, CyclePhase.CONTRACTION: 0.1},
            CyclePhase.EXPANSION: {CyclePhase.PEAK: 0.4, CyclePhase.EXPANSION: 0.5, CyclePhase.CONTRACTION: 0.1},
            CyclePhase.PEAK: {CyclePhase.CONTRACTION: 0.5, CyclePhase.PEAK: 0.3, CyclePhase.RECESSION: 0.2},
            CyclePhase.CONTRACTION: {CyclePhase.RECESSION: 0.4, CyclePhase.RECOVERY: 0.3, CyclePhase.CONTRACTION: 0.3},
            CyclePhase.RECESSION: {CyclePhase.RECOVERY: 0.5, CyclePhase.RECESSION: 0.4, CyclePhase.CONTRACTION: 0.1},
        }
        return transitions.get(current, {})

    def _sector_implications(self, phase: CyclePhase) -> Dict[str, str]:
        implications = {
            CyclePhase.RECOVERY: {
                "Consumer Discretionary": "FAVORABLE - early cycle beneficiary",
                "Technology": "FAVORABLE - growth recovery",
                "Industrials": "FAVORABLE - capex recovery",
            },
            CyclePhase.EXPANSION: {
                "Technology": "FAVORABLE - strong demand",
                "Industrials": "FAVORABLE - capacity expansion",
                "Energy": "FAVORABLE - rising demand",
            },
            CyclePhase.PEAK: {
                "Energy": "FAVORABLE - peak demand pricing",
                "Materials": "FAVORABLE - inflation hedge",
                "Consumer Staples": "NEUTRAL - rotation candidate",
            },
            CyclePhase.CONTRACTION: {
                "Healthcare": "FAVORABLE - defensive",
                "Consumer Staples": "FAVORABLE - defensive",
                "Utilities": "FAVORABLE - safe haven",
            },
            CyclePhase.RECESSION: {
                "Consumer Staples": "FAVORABLE - essential goods",
                "Healthcare": "FAVORABLE - non-discretionary",
                "Utilities": "FAVORABLE - stable cash flows",
            },
        }
        return implications.get(phase, {})
