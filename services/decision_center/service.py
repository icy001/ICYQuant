"""Decision Center Service – orchestrates the full Decision Intelligence pipeline.

This is the central hub that receives decisions from all intelligence engines,
fuses them, detects conflicts, validates compliance, arbitrates, and produces
the single Final Decision.
"""

from typing import Any, Dict, List, Optional

from .arbitration import DecisionArbitrationEngine
from .collector import DecisionCollector, DecisionPackage
from .compliance import ComplianceValidator
from .confidence import ConfidenceAggregator
from .conflict import ConflictDetectionEngine
from .final_decision import FinalDecision, FinalDecisionGenerator
from .fusion import MultiAgentFusionEngine
from .memory import DecisionMemory
from .timeline import DecisionTimeline


class DecisionCenterService:
    """Central Decision Hub — orchestrates the entire decision pipeline.

    Pipeline:
        Collection → Fusion → Conflict Detection → Confidence Aggregation
        → Compliance Validation → Arbitration → Final Decision → Timeline/Memory
    """

    def __init__(
        self,
        fusion_engine: MultiAgentFusionEngine,
        final_generator: FinalDecisionGenerator,
        collector: Optional[DecisionCollector] = None,
        conflict_engine: Optional[ConflictDetectionEngine] = None,
        confidence_aggregator: Optional[ConfidenceAggregator] = None,
        arbitration_engine: Optional[DecisionArbitrationEngine] = None,
        compliance_validator: Optional[ComplianceValidator] = None,
        timeline: Optional[DecisionTimeline] = None,
        memory: Optional[DecisionMemory] = None,
    ) -> None:
        self.fusion = fusion_engine
        self.generator = final_generator
        self.collector = collector or DecisionCollector()
        self.conflict_engine = conflict_engine or ConflictDetectionEngine()
        self.confidence_aggregator = confidence_aggregator or ConfidenceAggregator()
        self.arbitration = arbitration_engine or DecisionArbitrationEngine()
        self.compliance = compliance_validator or ComplianceValidator()
        self.timeline = timeline or DecisionTimeline()
        self.memory = memory or DecisionMemory()

    def decide(self, decisions: List[DecisionPackage]) -> Dict[str, Any]:
        """Simple decide: fuse → generate final output.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            Dict with signal and confidence.
        """
        result = self.fusion.fuse(decisions)
        return self.generator.build(result)

    def decide_full(
        self,
        decisions: List[DecisionPackage],
        risk_level: str = "MEDIUM",
        execution_plan: Optional[Dict[str, Any]] = None,
        compliance_approved: bool = True,
    ) -> Dict[str, Any]:
        """Run the complete decision pipeline.

        Pipeline:
        1. Collect decisions
        2. Fuse into consensus
        3. Detect conflicts
        4. Aggregate confidence
        5. Validate compliance
        6. Arbitrate (if conflict)
        7. Generate final decision
        8. Record in timeline and memory

        Args:
            decisions: list of DecisionPackages from intelligence engines.
            risk_level: risk assessment label.
            execution_plan: execution parameters.
            compliance_approved: overall compliance approval.

        Returns:
            Complete decision report dict.
        """
        # 1. Collect
        for d in decisions:
            self.collector.collect(d.source, d.signal, d.confidence)

        # 2. Fusion
        fused = self.fusion.fuse(decisions)
        conf_weighted = self.fusion.confidence_weighted_fuse(decisions)

        # 3. Conflict detection
        conflict = self.conflict_engine.analyze(decisions)

        # 4. Confidence aggregation
        overall_conf = self.confidence_aggregator.aggregate(decisions)
        conf_stats = self.confidence_aggregator.aggregate_stats(decisions)

        # 5. Compliance
        compliance_ok = self.compliance.validate(compliance_approved)

        # 6. Arbitration
        arbitration_result = self.arbitration.arbitrate(decisions)
        winner = arbitration_result["winner"]

        # 7. Final decision
        if winner:
            final = self.generator.build_full(
                decision=winner,
                reason=arbitration_result["rationale"],
                risk_level=risk_level,
                execution_plan=execution_plan,
                conflict_score=conflict.conflict_score,
                arbitration_method="priority" if conflict.has_conflict else "consensus",
            )
            final_dict = self.generator.to_dict(final)
        else:
            final_dict = {"signal": "HOLD", "confidence": 0.0, "reason": "No decision"}

        # 8. Record
        self.timeline.record(
            signal=final_dict["signal"],
            confidence=final_dict.get("confidence", 0.0),
            reason=final_dict.get("reason", ""),
        )
        self.memory.save(final_dict)

        return {
            "final_decision": final_dict,
            "fusion": {
                "winner": fused.signal if fused else None,
                "confidence_weighted": conf_weighted,
            },
            "conflict": {
                "has_conflict": conflict.has_conflict,
                "conflict_score": conflict.conflict_score,
                "details": conflict.details,
            },
            "confidence": {
                "overall": round(overall_conf, 4),
                "stats": conf_stats,
            },
            "compliance": {
                "approved": compliance_ok,
            },
            "arbitration": {
                "method": "priority" if conflict.has_conflict else "consensus",
                "rationale": arbitration_result["rationale"],
                "winner_source": winner.source if winner else None,
            },
        }
