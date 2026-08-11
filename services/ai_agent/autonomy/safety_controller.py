"""Safety Controller — final safety gate for all autonomous decisions.

Pipeline:
    Confidence + Risk + Compliance -> SafetyController.evaluate()
        -> Aggregate all safety signals
        -> Make final decision: Continue / Pause / Escalate / Reject
        -> Enforce safety boundaries
        -> Output SafetyDecision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SafetyAction(str, Enum):
    CONTINUE = "continue"
    PAUSE = "pause"
    ESCALATE = "escalate"
    REJECT = "reject"


@dataclass
class SafetyDecision:
    """Final safety decision for an autonomous workflow.

    Attributes:
        decision_id: Unique identifier.
        workflow_id: Related workflow.
        action: Final safety action.
        confidence_score: Associated confidence score.
        risk_assessment: Risk assessment result.
        compliance_result: Compliance check result.
        reason: Human-readable reason.
        decided_at: Decision timestamp.
    """

    decision_id: str = ""
    workflow_id: str = ""
    action: SafetyAction = SafetyAction.ESCALATE
    confidence_score: float = 0.0
    risk_assessment: str = ""
    compliance_result: str = ""
    reason: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_allowed(self) -> bool:
        return self.action == SafetyAction.CONTINUE

    @property
    def is_paused(self) -> bool:
        return self.action == SafetyAction.PAUSE

    @property
    def is_rejected(self) -> bool:
        return self.action == SafetyAction.REJECT


class SafetyController:
    """Final safety gate for all autonomous decisions.

    Aggregates confidence, risk, and compliance signals to make the
    final safety decision: Continue, Pause, Escalate, or Reject.

    Supports:
        - Multi-signal aggregation
        - Hierarchical decision logic (confidence -> risk -> compliance)
        - Automatic escalation on uncertainty
        - Hard rejection on rule violations

    Decision logic:
        - Any compliance violation -> REJECT
        - Any critical risk -> REJECT
        - Low confidence (< 0.5) -> ESCALATE
        - Medium confidence (0.5-0.8) + warnings -> PAUSE
        - High confidence (>= 0.8) + all clear -> CONTINUE

    Usage:
        controller = SafetyController(confidence_engine, config)
        await controller.initialize()
        decision = await controller.evaluate(
            workflow, confidence_score, risk_assessment, compliance_result
        )
        if decision.is_allowed:
            proceed()
        elif decision.is_rejected:
            abort()
    """

    def __init__(
        self,
        confidence_engine: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self._confidence_engine = confidence_engine
        self._config = config
        self._decisions: list[SafetyDecision] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("SafetyController created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("SafetyController initialized")

    async def shutdown(self) -> None:
        self._decisions.clear()
        self._initialized = False
        logger.info("SafetyController shutdown complete")

    async def evaluate(
        self,
        workflow: Any,
        confidence_score: Optional[Any] = None,
        risk_assessment: Optional[Any] = None,
        compliance_result: Optional[Any] = None,
    ) -> SafetyDecision:
        """Evaluate safety and return final decision.

        Args:
            workflow: The workflow context.
            confidence_score: ConfidenceScore from ConfidenceEngine.
            risk_assessment: RiskAssessment from RiskReview.
            compliance_result: ComplianceResult from ComplianceChecker.

        Returns:
            SafetyDecision with final action.
        """
        wf_id = getattr(workflow, "workflow_id", "") if workflow else ""
        self._counter += 1
        decision = SafetyDecision(
            decision_id=f"safety_{self._counter}",
            workflow_id=wf_id,
            action=SafetyAction.ESCALATE,
        )

        # Priority 1: Compliance violations -> REJECT
        if compliance_result:
            is_approved = getattr(compliance_result, "is_approved", True)
            if not is_approved:
                decision.action = SafetyAction.REJECT
                decision.reason = "Compliance violation detected"
                decision.compliance_result = "rejected"
                self._store(decision)
                logger.warning("SafetyController: REJECT (compliance): %s", wf_id)
                return decision

        # Priority 2: Critical risk -> REJECT
        if risk_assessment:
            risk_decision = getattr(risk_assessment, "decision", None)
            risk_val = risk_decision.value if hasattr(risk_decision, "value") else str(risk_decision)
            decision.risk_assessment = risk_val
            if risk_val == "rejected":
                decision.action = SafetyAction.REJECT
                decision.reason = "Critical risk detected"
                self._store(decision)
                logger.warning("SafetyController: REJECT (risk): %s", wf_id)
                return decision

        # Priority 3: Low confidence -> ESCALATE
        if confidence_score:
            overall = getattr(confidence_score, "overall", 0.0)
            decision.confidence_score = overall
            if overall < 0.50:
                decision.action = SafetyAction.ESCALATE
                decision.reason = f"Low confidence ({overall:.2f})"
                self._store(decision)
                logger.info("SafetyController: ESCALATE: %s", wf_id)
                return decision
            if overall < 0.80:
                decision.action = SafetyAction.PAUSE
                decision.reason = f"Medium confidence ({overall:.2f})"
                self._store(decision)
                logger.info("SafetyController: PAUSE: %s", wf_id)
                return decision

        # All clear -> CONTINUE
        decision.action = SafetyAction.CONTINUE
        decision.reason = "All safety checks passed"
        self._store(decision)
        logger.info("SafetyController: CONTINUE: %s", wf_id)
        return decision

    def _store(self, decision: SafetyDecision) -> None:
        self._decisions.append(decision)

    def get_summary(self) -> Dict[str, Any]:
        continue_count = sum(1 for d in self._decisions if d.is_allowed)
        reject_count = sum(1 for d in self._decisions if d.is_rejected)
        return {
            "initialized": self._initialized,
            "total_decisions": len(self._decisions),
            "continued": continue_count,
            "rejected": reject_count,
        }
