"""Macro Intelligence Service.

Orchestrates all macro intelligence components into a unified
analysis pipeline: collect → analyze → classify → adapt.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .adapter import MacroAdaptation, MacroStrategyAdapter
from .central_bank import CentralBankAnalysis, CentralBankIntelligence
from .classifier import MacroClassification, MacroRegimeClassifier
from .cycle import CycleResult, EconomicCycleDetector
from .data import (
    CentralBankEvent,
    IndicatorCategory,
    MacroDataSnapshot,
    MacroEvent,
    MacroIndicator,
    MacroRegime,
    MacroRegimeState,
)
from .event import EventImpactPrediction, EventImpactPredictor
from .inflation import InflationAnalysis, InflationAnalyzer
from .liquidity import LiquidityAnalysis, LiquidityEngine


@dataclass
class MacroIntelligenceReport:
    """Complete macro intelligence analysis report.

    The unified output of the Macro Intelligence Engine, containing
    all component analyses and the fused macro classification with
    strategy adaptation recommendations.

    Attributes:
        classification: Fused macro classification.
        adaptation: Strategy/portfolio adaptation.
        cycle: Economic cycle analysis.
        inflation: Inflation analysis.
        liquidity: Liquidity analysis.
        central_banks: Central bank analyses by bank.
        event_predictions: Upcoming event impact predictions.
        timestamp: Report generation timestamp.
        metadata: Additional report metadata.
    """
    classification: MacroClassification
    adaptation: MacroAdaptation
    cycle: CycleResult
    inflation: InflationAnalysis
    liquidity: LiquidityAnalysis
    central_banks: dict[str, CentralBankAnalysis] = field(default_factory=dict)
    event_predictions: list[EventImpactPrediction] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def regime(self) -> MacroRegime:
        return self.classification.regime

    @property
    def is_risk_on(self) -> bool:
        return self.regime.is_risk_on

    @property
    def is_risk_off(self) -> bool:
        return self.regime.is_risk_off

    @property
    def summary(self) -> str:
        lines = [
            f"=== Macro Intelligence Report ===",
            f"Regime: {self.regime.summary}",
            f"Cycle: {self.cycle.summary}",
            f"Inflation: {self.inflation.summary}",
            f"Liquidity: {self.liquidity.summary}",
            f"Adaptation: {self.adaptation.summary}",
            f"Risk Score: {self.classification.risk_score:.0%}",
            f"Opportunity Score: {self.classification.opportunity_score:.0%}",
        ]
        return "\n".join(lines)


class MacroIntelligenceService:
    """Unified macro intelligence analysis service.

    Orchestrates the full macro intelligence pipeline:
    1. Economic cycle detection
    2. Inflation analysis
    3. Liquidity analysis
    4. Central bank intelligence
    5. Event impact prediction
    6. Macro regime classification
    7. Strategy/portfolio adaptation
    """

    def __init__(self):
        self.cycle_detector = EconomicCycleDetector()
        self.inflation_analyzer = InflationAnalyzer()
        self.liquidity_engine = LiquidityEngine()
        self.central_bank_intel = CentralBankIntelligence()
        self.event_predictor = EventImpactPredictor()
        self.classifier = MacroRegimeClassifier()
        self.adapter = MacroStrategyAdapter()

        self._reports: list[MacroIntelligenceReport] = []

    def analyze(self, snapshot: MacroDataSnapshot,
                central_bank_events: Optional[list[CentralBankEvent]] = None,
                upcoming_events: Optional[list[MacroEvent]] = None) -> MacroIntelligenceReport:
        """Run the full macro intelligence analysis pipeline.

        Args:
            snapshot: Current macro data snapshot with all indicators.
            central_bank_events: Recent central bank events to analyze.
            upcoming_events: Upcoming macro events to predict.

        Returns:
            MacroIntelligenceReport with complete analysis.
        """
        # 1. Economic cycle detection
        cycle = self.cycle_detector.detect(snapshot)

        # 2. Inflation analysis
        inflation = self.inflation_analyzer.analyze(snapshot)

        # 3. Liquidity analysis
        liquidity = self.liquidity_engine.analyze(snapshot)

        # 4. Central bank intelligence
        central_banks: dict[str, CentralBankAnalysis] = {}
        if central_bank_events:
            for event in central_bank_events:
                analysis = self.central_bank_intel.analyze(event, snapshot)
                central_banks[event.bank] = analysis

        # 5. Event impact predictions
        event_predictions: list[EventImpactPrediction] = []
        if upcoming_events:
            for event in upcoming_events:
                prediction = self.event_predictor.predict(event, snapshot)
                event_predictions.append(prediction)

        # 6. Macro regime classification
        classification = self.classifier.classify_from_components(
            cycle=cycle,
            inflation=inflation,
            liquidity=liquidity,
            central_banks=central_banks,
        )

        # 7. Strategy/portfolio adaptation
        adaptation = self.adapter.adapt(classification)

        report = MacroIntelligenceReport(
            classification=classification,
            adaptation=adaptation,
            cycle=cycle,
            inflation=inflation,
            liquidity=liquidity,
            central_banks=central_banks,
            event_predictions=event_predictions,
            metadata={
                "indicators_analyzed": len(snapshot),
                "banks_analyzed": list(central_banks.keys()),
                "events_predicted": len(event_predictions),
            },
        )

        self._reports.append(report)
        return report

    def analyze_simple(self, data: dict[str, Any]) -> MacroIntelligenceReport:
        """Run analysis from a simple data dict.

        Convenience method for testing and quick analysis.

        Args:
            data: Dict with macro indicators and optional
                  central_bank_events and upcoming_events.

        Returns:
            MacroIntelligenceReport.
        """
        from .data import IndicatorCategory

        # Build snapshot from numeric values
        snapshot = MacroDataSnapshot()
        for key, value in data.items():
            if isinstance(value, (int, float)):
                snapshot.add(MacroIndicator(
                    name=key,
                    value=float(value),
                    category=IndicatorCategory.GROWTH,
                ))

        # Extract central bank events
        cb_events = data.get("central_bank_events", [])
        upcoming = data.get("upcoming_events", [])

        return self.analyze(snapshot, cb_events, upcoming)

    def analyze_quick(self, cycle_phase: str = "EXPANSION",
                      inflation_trend: str = "COOLING",
                      liquidity_condition: str = "LOOSE",
                      fed_sentiment: str = "dovish") -> MacroIntelligenceReport:
        """Quick analysis with minimal inputs.

        Convenience for rapid macro assessment.

        Args:
            cycle_phase: Economic cycle phase string.
            inflation_trend: Inflation trend string.
            liquidity_condition: Liquidity condition string.
            fed_sentiment: Fed sentiment ("dovish", "hawkish", "neutral").

        Returns:
            MacroIntelligenceReport.
        """
        from .cycle import CyclePhase
        from .inflation import InflationTrend
        from .liquidity import LiquidityCondition

        # Build minimal snapshot
        snapshot = MacroDataSnapshot()
        snapshot.add(MacroIndicator(
            name="GDP_Growth",
            value=3.0 if "EXPANSION" in cycle_phase.upper() else 1.0,
            category=IndicatorCategory.GROWTH,
        ))
        snapshot.add(MacroIndicator(
            name="CPI",
            value=3.5 if inflation_trend.upper() in ("RISING", "RAPIDLY_RISING") else 2.0,
            category=IndicatorCategory.INFLATION,
        ))
        snapshot.add(MacroIndicator(
            name="M2_Growth",
            value=8.0 if liquidity_condition.upper() in ("LOOSE", "EXTREMELY_LOOSE") else 3.0,
            category=IndicatorCategory.MONETARY,
        ))

        # Central bank event
        fed_event = CentralBankEvent(
            bank="FED",
            event_type="decision",
            date=datetime.utcnow(),
            rate_change=0.0,
            current_rate=5.25,
            sentiment=fed_sentiment,
            confidence=0.7,
        )

        return self.analyze(snapshot, central_bank_events=[fed_event])

    def get_reports(self) -> list[MacroIntelligenceReport]:
        """Get all generated reports."""
        return list(self._reports)

    def get_latest_report(self) -> Optional[MacroIntelligenceReport]:
        """Get the most recent report."""
        return self._reports[-1] if self._reports else None


__all__ = [
    "MacroIntelligenceReport",
    "MacroIntelligenceService",
]
