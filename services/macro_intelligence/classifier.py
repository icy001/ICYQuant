"""Macro Regime Classifier.

Fuses economic cycle, inflation, liquidity, and central bank
analyses into a unified macro regime classification that
drives strategy selection and portfolio adjustments.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .central_bank import CentralBankAnalysis, HawkDoveScale
from .cycle import CyclePhase, CycleResult
from .data import MacroDataSnapshot, MacroRegime, MacroRegimeState
from .inflation import InflationAnalysis, InflationRegime, InflationTrend
from .liquidity import LiquidityAnalysis, LiquidityCondition, LiquidityTrend


@dataclass
class MacroClassification:
    """Complete macro regime classification result.

    Fuses all macro intelligence dimensions into one unified view.

    Attributes:
        regime: The classified macro regime.
        cycle_result: Underlying economic cycle analysis.
        inflation_result: Underlying inflation analysis.
        liquidity_result: Underlying liquidity analysis.
        central_bank_results: Underlying central bank analyses.
        asset_allocation_bias: Recommended allocation bias by asset class.
        risk_score: Aggregate macro risk score (0-1, higher = riskier).
        opportunity_score: Macro opportunity score (0-1, higher = more opportunities).
        details: Additional classification details.
        timestamp: Classification timestamp.
    """
    regime: MacroRegime
    cycle_result: Optional[CycleResult] = None
    inflation_result: Optional[InflationAnalysis] = None
    liquidity_result: Optional[LiquidityAnalysis] = None
    central_bank_results: dict[str, CentralBankAnalysis] = field(default_factory=dict)
    asset_allocation_bias: dict[str, float] = field(default_factory=dict)
    risk_score: float = 0.5
    opportunity_score: float = 0.5
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_favorable(self) -> bool:
        return self.regime.is_risk_on

    @property
    def is_unfavorable(self) -> bool:
        return self.regime.is_risk_off

    @property
    def summary(self) -> str:
        parts = [
            f"Regime: {self.regime.summary}",
            f"Risk: {self.risk_score:.0%}",
            f"Opportunity: {self.opportunity_score:.0%}",
        ]
        return " | ".join(parts)


class MacroRegimeClassifier:
    """Classifies the macro regime from fused intelligence signals.

    Combines economic cycle, inflation, liquidity, and central bank
    analyses into a single macro regime classification with
    actionable investment implications.
    """

    # Regime classification matrix
    # Maps (cycle, inflation_regime, liquidity_condition) → MacroRegimeState
    _REGIME_MATRIX = {
        # ── Expansion + Stable/Cooling Inflation ──
        (CyclePhase.EXPANSION, InflationRegime.STABLE_INFLATION, LiquidityCondition.LOOSE):
            MacroRegimeState.GOLDILOCKS,
        (CyclePhase.EXPANSION, InflationRegime.DISINFLATION, LiquidityCondition.LOOSE):
            MacroRegimeState.GOLDILOCKS,
        (CyclePhase.EXPANSION, InflationRegime.STABLE_INFLATION, LiquidityCondition.NEUTRAL):
            MacroRegimeState.GOLDILOCKS,

        # ── Expansion + Rising Inflation ──
        (CyclePhase.EXPANSION, InflationRegime.REACCELERATION, LiquidityCondition.LOOSE):
            MacroRegimeState.REFLATION,
        (CyclePhase.EXPANSION, InflationRegime.REACCELERATION, LiquidityCondition.NEUTRAL):
            MacroRegimeState.OVERHEATING,
        (CyclePhase.LATE_CYCLE, InflationRegime.REACCELERATION, LiquidityCondition.TIGHT):
            MacroRegimeState.OVERHEATING,

        # ── Stagflation ──
        (CyclePhase.RECESSION, InflationRegime.STAGFLATION, LiquidityCondition.TIGHT):
            MacroRegimeState.STAGFLATION,
        (CyclePhase.CONTRACTION, InflationRegime.STAGFLATION, LiquidityCondition.TIGHT):
            MacroRegimeState.STAGFLATION,

        # ── Recession / Recovery ──
        (CyclePhase.RECESSION, InflationRegime.DISINFLATION, LiquidityCondition.TIGHT):
            MacroRegimeState.RECESSION,
        (CyclePhase.DEEP_RECESSION, InflationRegime.DEFLATION, LiquidityCondition.EXTREMELY_TIGHT):
            MacroRegimeState.RECESSION,
        (CyclePhase.EARLY_RECOVERY, InflationRegime.DISINFLATION, LiquidityCondition.SLIGHTLY_LOOSE):
            MacroRegimeState.RECOVERY,
        (CyclePhase.RECOVERY, InflationRegime.STABLE_INFLATION, LiquidityCondition.LOOSE):
            MacroRegimeState.RECOVERY,

        # ── Liquidity-driven ──
        (CyclePhase.EXPANSION, InflationRegime.STABLE_INFLATION, LiquidityCondition.EXTREMELY_LOOSE):
            MacroRegimeState.LIQUIDITY_SURGE,
        (CyclePhase.EXPANSION, InflationRegime.REACCELERATION, LiquidityCondition.EXTREMELY_TIGHT):
            MacroRegimeState.LIQUIDITY_CRUNCH,
    }

    def __init__(self):
        self._history: list[MacroClassification] = []

    def classify(self, snapshot: MacroDataSnapshot) -> MacroClassification:
        """Classify macro regime from a data snapshot.

        This is the simple/standalone classification path.

        Args:
            snapshot: Macro data snapshot.

        Returns:
            MacroClassification with the fused regime.
        """
        from .cycle import EconomicCycleDetector
        from .inflation import InflationAnalyzer
        from .liquidity import LiquidityEngine

        cycle_detector = EconomicCycleDetector()
        inflation_analyzer = InflationAnalyzer()
        liquidity_engine = LiquidityEngine()

        cycle = cycle_detector.detect(snapshot)
        inflation = inflation_analyzer.analyze(snapshot)
        liquidity = liquidity_engine.analyze(snapshot)

        return self._fuse(cycle, inflation, liquidity, {})

    def classify_from_components(self,
                                  cycle: CycleResult,
                                  inflation: InflationAnalysis,
                                  liquidity: LiquidityAnalysis,
                                  central_banks: dict[str, CentralBankAnalysis]) -> MacroClassification:
        """Classify macro regime from pre-computed component analyses.

        This is the preferred path when using the full service pipeline.

        Args:
            cycle: Economic cycle analysis result.
            inflation: Inflation analysis result.
            liquidity: Liquidity analysis result.
            central_banks: Dict of bank → central bank analysis.

        Returns:
            MacroClassification with the fused regime.
        """
        return self._fuse(cycle, inflation, liquidity, central_banks)

    def classify_from_dict(self, data: dict[str, Any]) -> MacroClassification:
        """Classify from a simple data dict.

        Convenience method for testing. Supports passing dicts
        with keys like cycle_phase, inflation_regime, etc.

        Args:
            data: Dict with component signals.

        Returns:
            MacroClassification result.
        """
        from .cycle import EconomicCycleDetector
        from .inflation import InflationAnalyzer
        from .liquidity import LiquidityEngine

        cycle_detector = EconomicCycleDetector()
        inflation_analyzer = InflationAnalyzer()
        liquidity_engine = LiquidityEngine()

        # Build snapshot from data
        snapshot = MacroDataSnapshot()
        from .data import MacroIndicator, IndicatorCategory

        for key, value in data.items():
            if isinstance(value, (int, float)):
                snapshot.add(MacroIndicator(
                    name=key,
                    value=float(value),
                    category=IndicatorCategory.GROWTH,
                ))

        cycle = cycle_detector.detect(snapshot)
        inflation = inflation_analyzer.analyze(snapshot)
        liquidity = liquidity_engine.analyze(snapshot)

        return self._fuse(cycle, inflation, liquidity, {})

    def get_history(self) -> list[MacroClassification]:
        """Get historical classifications."""
        return list(self._history)

    # ── Private helpers ─────────────────────────────────────────────

    def _fuse(self, cycle: CycleResult, inflation: InflationAnalysis,
              liquidity: LiquidityAnalysis,
              central_banks: dict[str, CentralBankAnalysis]) -> MacroClassification:
        """Fuse component analyses into unified macro classification."""
        # 1. Determine regime from matrix
        regime_state, confidence = self._match_regime(
            cycle.phase, inflation.regime, liquidity.condition,
        )

        # 2. Compute dimension scores
        growth_score = cycle.growth_momentum
        inflation_score = inflation.momentum
        liquidity_score = liquidity.composite_score

        # 3. Policy score from central bank consensus
        policy_score = self._compute_policy_score(central_banks)

        # 4. Build MacroRegime
        regime = MacroRegime(
            state=regime_state,
            confidence=confidence,
            growth_score=growth_score,
            inflation_score=inflation_score,
            liquidity_score=liquidity_score,
            policy_score=policy_score,
            details={
                "cycle_phase": cycle.phase.value,
                "inflation_regime": inflation.regime.value,
                "inflation_trend": inflation.trend.value,
                "liquidity_condition": liquidity.condition.value,
                "liquidity_trend": liquidity.trend.value,
            },
        )

        # 5. Risk and opportunity scores
        risk_score = self._compute_risk_score(regime, cycle, inflation, liquidity)
        opportunity_score = self._compute_opportunity_score(regime, cycle, liquidity)

        # 6. Asset allocation bias
        allocation_bias = self._compute_allocation_bias(regime_state)

        classification = MacroClassification(
            regime=regime,
            cycle_result=cycle,
            inflation_result=inflation,
            liquidity_result=liquidity,
            central_bank_results=central_banks,
            asset_allocation_bias=allocation_bias,
            risk_score=risk_score,
            opportunity_score=opportunity_score,
            details={
                "components": {
                    "cycle": cycle.phase.value,
                    "inflation": inflation.regime.value,
                    "liquidity": liquidity.condition.value,
                    "banks_analyzed": list(central_banks.keys()),
                },
            },
        )

        self._history.append(classification)
        return classification

    def _match_regime(self, cycle_phase: CyclePhase,
                      inflation_regime: InflationRegime,
                      liquidity_condition: LiquidityCondition) -> tuple[MacroRegimeState, float]:
        """Match to a macro regime state."""
        # Direct lookup
        key = (cycle_phase, inflation_regime, liquidity_condition)
        if key in self._REGIME_MATRIX:
            return self._REGIME_MATRIX[key], 0.70

        # Fuzzy matching: try matching just cycle + inflation
        for (cp, ir, _lc), regime in self._REGIME_MATRIX.items():
            if cp == cycle_phase and ir == inflation_regime:
                return regime, 0.55

        # Broad matching from cycle phase
        if cycle_phase in (CyclePhase.EXPANSION, CyclePhase.EARLY_EXPANSION):
            if inflation_regime == InflationRegime.DISINFLATION:
                return MacroRegimeState.GOLDILOCKS, 0.50
            return MacroRegimeState.REFLATION, 0.45
        elif cycle_phase in (CyclePhase.RECESSION, CyclePhase.DEEP_RECESSION):
            return MacroRegimeState.RECESSION, 0.55
        elif cycle_phase in (CyclePhase.RECOVERY, CyclePhase.EARLY_RECOVERY):
            return MacroRegimeState.RECOVERY, 0.50
        elif cycle_phase == CyclePhase.LATE_CYCLE:
            return MacroRegimeState.OVERHEATING, 0.45

        return MacroRegimeState.GOLDILOCKS, 0.35  # default

    def _compute_policy_score(self,
                               central_banks: dict[str, CentralBankAnalysis]) -> float:
        """Compute aggregate policy score from central bank analyses.

        Negative = hawkish/tightening, Positive = dovish/easing.
        """
        if not central_banks:
            return 0.0

        scores = []
        weights = {"FED": 0.35, "ECB": 0.25, "BOJ": 0.15, "PBOC": 0.10, "BOE": 0.10, "OTHER": 0.05}

        for bank, analysis in central_banks.items():
            weight = weights.get(bank, weights["OTHER"] / max(1, len(central_banks)))

            if analysis.is_dovish:
                scores.append(0.5 * weight)
            elif analysis.is_hawkish:
                scores.append(-0.5 * weight)
            else:
                scores.append(0.0)

        return max(-1.0, min(1.0, sum(scores)))

    @staticmethod
    def _compute_risk_score(regime: MacroRegime,
                            cycle: CycleResult,
                            inflation: InflationAnalysis,
                            liquidity: LiquidityAnalysis) -> float:
        """Compute aggregate macro risk score (0-1)."""
        score = 0.3  # base

        # Cycle risk
        if cycle.is_contractionary:
            score += 0.25
        elif cycle.phase == CyclePhase.LATE_CYCLE:
            score += 0.15

        # Inflation risk
        if inflation.is_problematic:
            score += 0.2
        elif inflation.is_rising:
            score += 0.1

        # Liquidity risk
        if liquidity.is_restrictive:
            score += 0.2
        elif not liquidity.is_accommodative:
            score += 0.1

        return min(1.0, max(0.0, score))

    @staticmethod
    def _compute_opportunity_score(regime: MacroRegime,
                                   cycle: CycleResult,
                                   liquidity: LiquidityAnalysis) -> float:
        """Compute macro opportunity score (0-1)."""
        score = 0.5  # base

        if cycle.is_expansionary:
            score += 0.2

        if liquidity.is_accommodative:
            score += 0.15

        if regime.is_risk_on:
            score += 0.1

        if regime.is_risk_off:
            score -= 0.15

        return min(1.0, max(0.0, score))

    @staticmethod
    def _compute_allocation_bias(state: MacroRegimeState) -> dict[str, float]:
        """Compute recommended allocation bias by asset class.

        Returns a dict of asset → bias weight (-1 to 1, positive = overweight).
        """
        biases = {
            MacroRegimeState.GOLDILOCKS: {
                "equities": 1.0, "bonds": -0.3, "commodities": 0.2,
                "cash": -0.5, "gold": -0.3,
            },
            MacroRegimeState.REFLATION: {
                "equities": 0.7, "bonds": -0.5, "commodities": 0.8,
                "cash": -0.3, "gold": 0.2,
            },
            MacroRegimeState.OVERHEATING: {
                "equities": 0.3, "bonds": -0.7, "commodities": 0.6,
                "cash": 0.2, "gold": 0.4,
            },
            MacroRegimeState.STAGFLATION: {
                "equities": -0.5, "bonds": -0.3, "commodities": 0.7,
                "cash": 0.5, "gold": 0.8,
            },
            MacroRegimeState.RECESSION: {
                "equities": -0.7, "bonds": 1.0, "commodities": -0.3,
                "cash": 0.3, "gold": 0.5,
            },
            MacroRegimeState.RECOVERY: {
                "equities": 0.8, "bonds": 0.2, "commodities": 0.4,
                "cash": -0.3, "gold": -0.2,
            },
            MacroRegimeState.EASING: {
                "equities": 0.6, "bonds": 0.7, "commodities": 0.3,
                "cash": -0.5, "gold": 0.4,
            },
            MacroRegimeState.TIGHTENING: {
                "equities": -0.3, "bonds": -0.5, "commodities": 0.0,
                "cash": 0.6, "gold": 0.0,
            },
            MacroRegimeState.LIQUIDITY_SURGE: {
                "equities": 1.0, "bonds": -0.2, "commodities": 0.6,
                "cash": -0.7, "gold": 0.2,
            },
            MacroRegimeState.LIQUIDITY_CRUNCH: {
                "equities": -0.8, "bonds": 0.3, "commodities": -0.5,
                "cash": 1.0, "gold": 0.6,
            },
        }

        return biases.get(state, {
            "equities": 0.0, "bonds": 0.0, "commodities": 0.0,
            "cash": 0.0, "gold": 0.0,
        })


__all__ = [
    "MacroClassification",
    "MacroRegimeClassifier",
]
