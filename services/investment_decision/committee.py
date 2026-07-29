from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .bull_agent import BullCaseAgent, BullCaseAnalysis
from .bear_agent import BearCaseAgent, BearCaseAnalysis
from .conviction import ConvictionScoreEngine


class VoteType(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    ABSTAIN = "ABSTAIN"


class MemberRole(str, Enum):
    BULL_ANALYST = "BULL_ANALYST"
    BEAR_ANALYST = "BEAR_ANALYST"
    RISK_ANALYST = "RISK_ANALYST"
    PORTFOLIO_MANAGER = "PORTFOLIO_MANAGER"


@dataclass
class CommitteeVote:
    member: str
    role: MemberRole
    vote: VoteType
    reason: str
    confidence: float = 0.0


@dataclass
class CommitteeDecision:
    symbol: str
    thesis_title: str
    votes: List[CommitteeVote]
    consensus: VoteType
    consensus_confidence: float
    debate_summary: str = ""
    challenges: List[str] = field(default_factory=list)
    approved: bool = False
    conditions: List[str] = field(default_factory=list)


class AIInvestmentCommittee:
    """AI Investment Committee - simulates an institutional investment committee with debate and voting."""

    def __init__(self):
        self.bull_agent = BullCaseAgent()
        self.bear_agent = BearCaseAgent()
        self.conviction_engine = ConvictionScoreEngine()
        self.decisions: List[CommitteeDecision] = []

    def discuss(self, thesis):
        """Conduct a committee discussion on an investment thesis.

        Args:
            thesis: The investment thesis to discuss (str, dict, or CommitteeDecision).

        Returns:
            Dict containing the committee decision.
        """
        if isinstance(thesis, CommitteeDecision):
            return self._process_decision(thesis)
        if isinstance(thesis, dict):
            return self._discuss_dict(thesis)
        return {"decision": thesis}

    def _discuss_dict(self, thesis_data: dict) -> dict:
        symbol = thesis_data.get("symbol", "UNKNOWN")
        thesis_title = thesis_data.get("title", "")

        # Bull case analysis
        bull_case = self.bull_agent.analyze({
            "symbol": symbol,
            "thesis": thesis_data,
        })

        # Bear case analysis
        bear_case = self.bear_agent.analyze({
            "symbol": symbol,
            "thesis": thesis_data,
        })

        # Committee members vote
        votes = self._collect_votes(symbol, thesis_title, thesis_data, bull_case, bear_case)

        # Determine consensus
        consensus, confidence = self._determine_consensus(votes)

        # Score conviction
        conviction_result = self.conviction_engine.score({
            "bull_case": bull_case,
            "bear_case": bear_case,
            "votes": votes,
        })

        decision = CommitteeDecision(
            symbol=symbol,
            thesis_title=thesis_title,
            votes=votes,
            consensus=consensus,
            consensus_confidence=round(confidence, 2),
            debate_summary=self._summarize_debate(bull_case, bear_case, votes),
            challenges=bear_case.get("bear_case", {}).get("risk_factors", []),
            approved=consensus in (VoteType.STRONG_BUY, VoteType.BUY),
            conditions=self._extract_conditions(bull_case, bear_case),
        )
        self.decisions.append(decision)
        return self._to_dict(decision)

    def _process_decision(self, decision: CommitteeDecision) -> dict:
        self.decisions.append(decision)
        return self._to_dict(decision)

    def _collect_votes(
        self,
        symbol: str,
        thesis_title: str,
        thesis_data: dict,
        bull_case: dict,
        bear_case: dict,
    ) -> List[CommitteeVote]:
        votes = []

        # Bull Analyst vote
        bull_score = bull_case.get("bull_case", {}).get("bullish_conviction", 0.6)
        if bull_score > 0.8:
            bull_vote = VoteType.STRONG_BUY
        elif bull_score > 0.6:
            bull_vote = VoteType.BUY
        elif bull_score > 0.4:
            bull_vote = VoteType.HOLD
        else:
            bull_vote = VoteType.SELL

        votes.append(CommitteeVote(
            member="Bull Analyst",
            role=MemberRole.BULL_ANALYST,
            vote=bull_vote,
            reason=f"Bullish conviction: {bull_score:.0%}. "
                   f"Key catalysts: {bull_case.get('bull_case', {}).get('catalysts', [])}",
            confidence=round(bull_score, 2),
        ))

        # Bear Analyst vote
        bear_risk_score = bear_case.get("bear_case", {}).get("risk_intensity", 0.3)
        if bear_risk_score > 0.7:
            bear_vote = VoteType.STRONG_SELL
        elif bear_risk_score > 0.5:
            bear_vote = VoteType.SELL
        elif bear_risk_score > 0.3:
            bear_vote = VoteType.HOLD
        else:
            bear_vote = VoteType.BUY

        votes.append(CommitteeVote(
            member="Bear Analyst",
            role=MemberRole.BEAR_ANALYST,
            vote=bear_vote,
            reason=f"Risk intensity: {bear_risk_score:.0%}. "
                   f"Key risks: {bear_case.get('bear_case', {}).get('risk_factors', [])}",
            confidence=round(1 - bear_risk_score, 2),
        ))

        # Risk Analyst vote
        risk_level = bear_risk_score
        if risk_level > 0.6:
            risk_vote = VoteType.SELL
        elif risk_level > 0.4:
            risk_vote = VoteType.HOLD
        else:
            risk_vote = VoteType.BUY

        votes.append(CommitteeVote(
            member="Risk Analyst",
            role=MemberRole.RISK_ANALYST,
            vote=risk_vote,
            reason=f"Risk assessment: {risk_level:.0%}. "
                   f"Risk-adjusted return assessment.",
            confidence=round(1 - risk_level, 2),
        ))

        # Portfolio Manager vote (synthesizes all views)
        avg_bullish = (bull_score + (1 - bear_risk_score)) / 2
        if avg_bullish > 0.75:
            pm_vote = VoteType.STRONG_BUY
        elif avg_bullish > 0.6:
            pm_vote = VoteType.BUY
        elif avg_bullish > 0.4:
            pm_vote = VoteType.HOLD
        elif avg_bullish > 0.25:
            pm_vote = VoteType.SELL
        else:
            pm_vote = VoteType.STRONG_SELL

        votes.append(CommitteeVote(
            member="Portfolio Manager",
            role=MemberRole.PORTFOLIO_MANAGER,
            vote=pm_vote,
            reason=f"Synthesized view: bull conviction {bull_score:.0%}, "
                   f"risk level {bear_risk_score:.0%}. "
                   f"Portfolio fit assessment complete.",
            confidence=round(avg_bullish, 2),
        ))

        return votes

    def _determine_consensus(self, votes: List[CommitteeVote]) -> tuple:
        """Determine the consensus from committee votes."""
        vote_values = {
            VoteType.STRONG_BUY: 5,
            VoteType.BUY: 4,
            VoteType.HOLD: 3,
            VoteType.SELL: 2,
            VoteType.STRONG_SELL: 1,
            VoteType.ABSTAIN: 3,
        }

        scores = [vote_values[v.vote] for v in votes]
        avg_score = sum(scores) / len(scores)
        confidence = 1 - (max(scores) - min(scores)) / 4 if len(scores) > 1 else 0.5

        if avg_score >= 4.5:
            consensus = VoteType.STRONG_BUY
        elif avg_score >= 3.5:
            consensus = VoteType.BUY
        elif avg_score >= 2.5:
            consensus = VoteType.HOLD
        elif avg_score >= 1.5:
            consensus = VoteType.SELL
        else:
            consensus = VoteType.STRONG_SELL

        return consensus, confidence

    def _summarize_debate(self, bull_case: dict, bear_case: dict, votes: List[CommitteeVote]) -> str:
        bull_summary = bull_case.get("bull_case", {}).get("narrative", "No bull case")
        bear_summary = bear_case.get("bear_case", {}).get("narrative", "No bear case")
        vote_summary = ", ".join([f"{v.member}: {v.vote.value}" for v in votes])
        return f"Bull: {bull_summary}. Bear: {bear_summary}. Votes: {vote_summary}."

    def _extract_conditions(self, bull_case: dict, bear_case: dict) -> List[str]:
        conditions = []
        bull_conditions = bull_case.get("bull_case", {}).get("required_conditions", [])
        if bull_conditions:
            conditions.extend(bull_conditions)
        bear_conditions = bear_case.get("bear_case", {}).get("invalidation_points", [])
        if bear_conditions:
            conditions.extend(bear_conditions)
        return conditions

    def _to_dict(self, decision: CommitteeDecision) -> dict:
        return {
            "decision": {
                "symbol": decision.symbol,
                "thesis_title": decision.thesis_title,
                "votes": [
                    {
                        "member": v.member,
                        "role": v.role.value,
                        "vote": v.vote.value,
                        "reason": v.reason,
                        "confidence": v.confidence,
                    }
                    for v in decision.votes
                ],
                "consensus": decision.consensus.value,
                "consensus_confidence": decision.consensus_confidence,
                "debate_summary": decision.debate_summary,
                "challenges": decision.challenges,
                "approved": decision.approved,
                "conditions": decision.conditions,
            }
        }

    def get_decisions(self) -> List[CommitteeDecision]:
        """Get all committee decisions."""
        return list(self.decisions)
