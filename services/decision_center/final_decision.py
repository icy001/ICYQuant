"""Final Decision Generator – produces the system's single source of truth."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .collector import DecisionPackage


@dataclass
class FinalDecision:
    """The single, authoritative trading decision for the entire system."""

    signal: str
    confidence: float
    reason: str = ""
    risk_level: str = "UNKNOWN"
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    conflict_score: float = 0.0
    arbitration_method: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class FinalDecisionGenerator:
    """Builds the FinalDecision — the system's single source of truth.

    This is the last step before the decision is handed off to the Execution Engine.
    """

    def build(self, decision: DecisionPackage) -> Dict[str, Any]:
        """Build a minimal final decision dict from a DecisionPackage.

        Args:
            decision: the winning DecisionPackage.

        Returns:
            Dict with signal and confidence.
        """
        return {
            "signal": decision.signal,
            "confidence": decision.confidence,
        }

    def build_full(
        self,
        decision: DecisionPackage,
        reason: str = "",
        risk_level: str = "MEDIUM",
        execution_plan: Optional[Dict[str, Any]] = None,
        conflict_score: float = 0.0,
        arbitration_method: str = "priority",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FinalDecision:
        """Build a complete FinalDecision with all context.

        Args:
            decision: the winning DecisionPackage.
            reason: human-readable rationale.
            risk_level: risk assessment label.
            execution_plan: execution parameters.
            conflict_score: conflict detection score.
            arbitration_method: how the decision was resolved.
            metadata: additional context.

        Returns:
            A FinalDecision dataclass instance.
        """
        return FinalDecision(
            signal=decision.signal,
            confidence=decision.confidence,
            reason=reason,
            risk_level=risk_level,
            execution_plan=execution_plan or {},
            source=decision.source,
            conflict_score=conflict_score,
            arbitration_method=arbitration_method,
            metadata=metadata or {},
        )

    def to_dict(self, final_decision: FinalDecision) -> Dict[str, Any]:
        """Serialize FinalDecision to dict."""
        return {
            "signal": final_decision.signal,
            "confidence": final_decision.confidence,
            "reason": final_decision.reason,
            "risk_level": final_decision.risk_level,
            "execution_plan": final_decision.execution_plan,
            "timestamp": final_decision.timestamp.isoformat(),
            "source": final_decision.source,
            "conflict_score": final_decision.conflict_score,
            "arbitration_method": final_decision.arbitration_method,
            "metadata": final_decision.metadata,
        }
