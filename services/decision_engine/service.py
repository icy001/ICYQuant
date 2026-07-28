from typing import Any, Dict, List, Optional

from .approval import ApprovalWorkflow
from .audit import DecisionAudit
from .decision import Decision
from .fusion import SignalFusionEngine
from .ranking import StrategyRankingEngine, StrategyScore
from .scoring import DecisionScoringEngine
from .selector import Candidate, RiskAdjustedSelector


class DecisionService:
    """Orchestrates the full decision pipeline.

    Pipeline: Signal Fusion -> Scoring -> Risk Check -> Ranking -> Approval -> Audit
    """

    def __init__(
        self,
        fusion: SignalFusionEngine,
        scoring: Optional[DecisionScoringEngine] = None,
        selector: Optional[RiskAdjustedSelector] = None,
        ranking: Optional[StrategyRankingEngine] = None,
        approval: Optional[ApprovalWorkflow] = None,
        audit: Optional[DecisionAudit] = None,
    ):
        self.fusion = fusion
        self.scoring = scoring or DecisionScoringEngine()
        self.selector = selector or RiskAdjustedSelector()
        self.ranking = ranking or StrategyRankingEngine()
        self.approval = approval or ApprovalWorkflow()
        self.audit = audit or DecisionAudit()

    def decide(self, signals: List[float]) -> float:
        """Simple decision: fuse signals and return the combined score."""
        return self.fusion.combine(signals)

    def decide_full(
        self,
        symbol: str,
        signals: List[float],
        alpha: float = 0.0,
        risk: float = 0.0,
        auto_approve: bool = False,
    ) -> Decision:
        """Full decision pipeline for a single symbol.

        Args:
            symbol: Asset symbol.
            signals: List of raw signal values.
            alpha: Alpha score.
            risk: Risk penalty.
            auto_approve: If True, auto-approve decisions above threshold.

        Returns:
            A Decision object with full pipeline results.
        """
        # Step 1: Fuse signals
        fused_score = self.fusion.combine(signals)

        # Step 2: Score
        score_result = self.scoring.score_full(
            alpha=alpha or fused_score,
            risk_penalty=risk,
        )

        # Step 3: Determine action
        action = self.scoring.determine_action(alpha, risk)

        # Step 4: Create decision
        decision = Decision(
            symbol=symbol,
            action=action,
            score=score_result["final_score"],
            reason=f"Fused {len(signals)} signals, alpha={alpha}, risk={risk}",
        )

        # Step 5: Approval
        if auto_approve:
            self.approval.auto_approve(decision)
        else:
            self.approval.submit(decision)

        # Step 6: Audit
        self.audit.record(decision)

        return decision

    def decide_weighted(
        self,
        symbol: str,
        signals: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> Decision:
        """Decision with weighted signal fusion."""
        fused = self.fusion.combine_weighted(signals, weights)

        action = "BUY" if fused > 0.3 else ("SELL" if fused < -0.3 else "HOLD")

        decision = Decision(
            symbol=symbol,
            action=action,
            score=round(fused, 4),
            signals=signals,
            reason=f"Weighted fusion of {len(signals)} signals",
        )

        self.approval.submit(decision)
        self.audit.record(decision)
        return decision

    def rank_strategies(
        self, strategies: List[StrategyScore]
    ) -> List[StrategyScore]:
        """Rank strategies by composite score."""
        return self.ranking.rank_by_composite(strategies)

    def select_best(
        self, candidates: List[Candidate]
    ) -> Optional[Candidate]:
        """Select the best candidate with risk adjustment."""
        return self.selector.select_with_score(candidates)

    def approve_decision(
        self, decision: Decision, approved: bool, reason: str = ""
    ) -> Decision:
        """Approve or reject a pending decision."""
        if approved:
            result = self.approval.approve(decision)
        else:
            result = self.approval.reject(decision, reason)
        self.audit.record(result)
        return result

    def execute_decision(self, decision: Decision) -> Decision:
        """Execute an approved decision."""
        result = self.approval.execute(decision)
        self.audit.record(result)
        return result

    def pipeline_summary(self) -> Dict[str, Any]:
        """Summary of the entire decision pipeline state."""
        return {
            "approval": self.approval.summary(),
            "audit": self.audit.summary(),
        }
