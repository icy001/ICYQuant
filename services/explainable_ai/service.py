"""Explainable AI Service – orchestrates the full XAI pipeline."""

from typing import Any, Dict, List, Optional

from .attribution import SignalAttributionEngine
from .audit import ModelAuditEngine
from .collector import DecisionCollector, DecisionEvent
from .confidence import ConfidenceAnalyzer
from .decision_path import DecisionPathEngine
from .explanation import HumanExplanationGenerator
from .importance import FeatureImportanceAnalyzer
from .memory import ExplainableMemory
from .validation import RuleValidationEngine, ValidationStatus


class ExplainableAIService:
    """Orchestrates all XAI components to produce explainable AI decisions.

    This is the main entry point for the AI Explainable Intelligence Engine.
    It wires together the decision collector, attribution engine, feature importance
    analyzer, decision path engine, confidence analyzer, rule validation engine,
    model audit engine, human explanation generator, and explainable memory.
    """

    def __init__(
        self,
        generator: HumanExplanationGenerator,
        collector: Optional[DecisionCollector] = None,
        attribution: Optional[SignalAttributionEngine] = None,
        importance: Optional[FeatureImportanceAnalyzer] = None,
        path_engine: Optional[DecisionPathEngine] = None,
        confidence: Optional[ConfidenceAnalyzer] = None,
        validation: Optional[RuleValidationEngine] = None,
        audit: Optional[ModelAuditEngine] = None,
        memory: Optional[ExplainableMemory] = None,
    ) -> None:
        self.generator = generator
        self.collector = collector or DecisionCollector()
        self.attribution = attribution or SignalAttributionEngine()
        self.importance = importance or FeatureImportanceAnalyzer()
        self.path_engine = path_engine or DecisionPathEngine()
        self.confidence = confidence or ConfidenceAnalyzer()
        self.validation = validation or RuleValidationEngine()
        self.audit = audit or ModelAuditEngine()
        self.memory = memory or ExplainableMemory()

    def explain(self, signal: str) -> str:
        """Generate a simple explanation for a signal."""
        return self.generator.generate(signal)

    def explain_full(
        self,
        signal: str,
        symbol: Optional[str] = None,
        probability: float = 0.0,
        scores: Optional[Dict[str, float]] = None,
        features: Optional[Dict[str, float]] = None,
        path_nodes: Optional[List[str]] = None,
        risk_ok: bool = True,
        position_ok: bool = True,
        model_name: str = "default",
        reasons: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the full XAI pipeline for a single decision.

        Args:
            signal: trading signal (e.g. "BUY", "SELL").
            symbol: instrument symbol.
            probability: raw model probability (0-1).
            scores: module contribution scores.
            features: feature importance map.
            path_nodes: decision path reasoning steps.
            risk_ok: risk check result.
            position_ok: position check result.
            model_name: model identifier for audit.
            reasons: human-readable reasons.

        Returns:
            Complete explainable report dictionary.
        """
        # 1. Collect decision
        event = self.collector.collect(
            strategy=model_name,
            signal=signal,
            confidence=probability,
            symbol=symbol,
            source="explainable_ai",
        )

        # 2. Signal attribution
        attribution = self.attribution.analyze(scores) if scores else {}

        # 3. Feature importance ranking
        feature_ranking = self.importance.rank(features) if features else []

        # 4. Decision path
        path = self.path_engine.build(path_nodes) if path_nodes else ""

        # 5. Confidence analysis
        conf_analysis = self.confidence.analyze(probability)

        # 6. Rule validation
        validation_passed = self.validation.validate(risk_ok, position_ok)

        # 7. Model audit
        audit_record = self.audit.record(model=model_name)

        # 8. Human explanation
        explanation = self.generator.generate_detailed(
            signal=signal,
            symbol=symbol,
            attribution=attribution,
            confidence=conf_analysis["confidence_score"],
            reasons=reasons,
            risk_level="Low" if validation_passed else "High",
        )

        # 9. Save to memory
        report = {
            "signal": signal,
            "symbol": symbol,
            "attribution": attribution,
            "feature_importance": feature_ranking,
            "decision_path": path,
            "confidence": conf_analysis,
            "validation_passed": validation_passed,
            "audit": {
                "model": audit_record.model,
                "status": audit_record.status,
                "model_version": audit_record.model_version,
            },
            "explanation": explanation,
        }
        self.memory.save(report)

        return report
