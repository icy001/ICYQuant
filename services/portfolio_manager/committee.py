"""Investment Committee Workflow – institutional approval process."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

from .manager import PortfolioProposal


@dataclass
class CommitteeReview:
    """A review step in the investment committee workflow."""

    step: str  # "research", "risk_review", "committee_vote", "approval"
    reviewer: str
    decision: str  # "approved", "rejected", "needs_revision"
    comments: str = ""
    score: float = 0.0  # 0-100

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "reviewer": self.reviewer,
            "decision": self.decision,
            "comments": self.comments,
            "score": self.score,
        }


@dataclass
class CommitteeResult:
    """Final result of the investment committee workflow."""

    proposal_id: str
    approved: bool
    reviews: List[CommitteeReview] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    final_score: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "approved": self.approved,
            "reviews": [r.to_dict() for r in self.reviews],
            "conditions": self.conditions,
            "final_score": self.final_score,
            "summary": self.summary,
        }


class InvestmentCommittee:
    """Simulates an institutional investment committee approval workflow.

    Runs proposals through: AI Research → Risk Review → Committee Vote →
    Final Approval, with scoring and conditional acceptance.
    """

    def __init__(
        self,
        auto_approve_threshold: float = 70.0,
        require_unanimous: bool = False,
    ):
        self.auto_approve_threshold = auto_approve_threshold
        self.require_unanimous = require_unanimous

    def approve(self, proposal: Any) -> dict:
        """Approve a proposal – supports PortfolioProposal, dict, or simple input.

        For dict/PortfolioProposal inputs, runs the full committee workflow.
        For simple inputs, returns a basic approval (legacy interface).
        """
        if isinstance(proposal, PortfolioProposal):
            result = self.run_workflow(proposal)
            return {"approved": result.approved}
        elif isinstance(proposal, dict):
            # Simple dict-based approval
            return self._approve_dict(proposal)
        else:
            return {"approved": True}

    def _approve_dict(self, proposal: dict) -> dict:
        """Simple approval for dict proposals."""
        props = PortfolioProposal(
            portfolio_id=proposal.get("portfolio_id", "unknown"),
            proposal_id=proposal.get("proposal_id", str(uuid.uuid4())[:8]),
            description=proposal.get("description", ""),
            rationale=proposal.get("rationale", ""),
        )
        result = self.run_workflow(props)
        return {"approved": result.approved}

    def run_workflow(self, proposal: PortfolioProposal) -> CommitteeResult:
        """Run the full investment committee workflow.

        Steps:
        1. AI Research Review – scores alpha and signal quality
        2. Risk Review – scores risk metrics and constraints
        3. Committee Vote – aggregates scores
        4. Final Approval – decides approve/reject/conditions
        """
        reviews: List[CommitteeReview] = []
        conditions: List[str] = []

        # Step 1: AI Research Review
        research_score = self._evaluate_research(proposal)
        research_decision = "approved" if research_score >= 50 else "needs_revision"
        reviews.append(CommitteeReview(
            step="research",
            reviewer="AI Research Agent",
            decision=research_decision,
            comments=f"Alpha quality score: {research_score:.0f}/100",
            score=research_score,
        ))

        # Step 2: Risk Review
        risk_score = 100.0 - proposal.risk_score
        risk_decision = "approved" if risk_score >= 50 else "needs_revision"
        if proposal.risk_score > 60:
            conditions.append("Reduce single-position risk.")
            conditions.append("Monitor drawdown daily.")
        reviews.append(CommitteeReview(
            step="risk_review",
            reviewer="Risk Intelligence Engine",
            decision=risk_decision,
            comments=f"Risk compliance score: {risk_score:.0f}/100",
            score=risk_score,
        ))

        # Step 3: Committee Vote
        final_score = (research_score + risk_score) / 2.0
        if self.require_unanimous:
            all_approved = all(r.decision == "approved" for r in reviews)
            vote_decision = "approved" if all_approved else "rejected"
        else:
            vote_decision = "approved" if final_score >= self.auto_approve_threshold else "needs_revision"

        reviews.append(CommitteeReview(
            step="committee_vote",
            reviewer="Investment Committee",
            decision=vote_decision,
            comments=f"Composite score: {final_score:.0f}/100",
            score=final_score,
        ))

        # Step 4: Final Decision
        if final_score >= self.auto_approve_threshold:
            if conditions:
                summary = f"APPROVED with {len(conditions)} conditions. Score: {final_score:.0f}/100."
            else:
                summary = f"APPROVED. Score: {final_score:.0f}/100."
            approved = True
        else:
            summary = f"NOT APPROVED. Score {final_score:.0f}/100 below threshold {self.auto_approve_threshold:.0f}."
            approved = False

        # Update proposal status
        proposal.status = "approved" if approved else "rejected"

        return CommitteeResult(
            proposal_id=proposal.proposal_id,
            approved=approved,
            reviews=reviews,
            conditions=conditions,
            final_score=final_score,
            summary=summary,
        )

    def _evaluate_research(self, proposal: PortfolioProposal) -> float:
        """Evaluate alpha/signal quality for the proposal."""
        # Base score from impact
        impact = proposal.expected_impact
        if impact:
            avg_impact = sum(abs(v) for v in impact.values()) / max(len(impact), 1)
            base = min(avg_impact * 200, 80)
        else:
            base = 50

        # Boost if clear rationale
        if proposal.rationale and len(proposal.rationale) > 20:
            base += 10

        return min(base, 100)
