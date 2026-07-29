"""Consensus Decision Engine - aggregates multi-agent opinions into unified decisions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DecisionType(Enum):
    """Type of investment decision."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    NO_ACTION = "NO_ACTION"
    HEDGE = "HEDGE"
    EXIT = "EXIT"


class VotingMethod(Enum):
    """Method for aggregating agent votes."""
    MAJORITY = "MAJORITY"
    WEIGHTED = "WEIGHTED"
    UNANIMOUS = "UNANIMOUS"
    SUPERMAJORITY = "SUPERMAJORITY"
    CONSENSUS_SCORE = "CONSENSUS_SCORE"


class ConfidenceLevel(Enum):
    """Confidence level of a decision."""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


@dataclass
class AgentOpinion:
    """Opinion from a single agent."""
    agent_id: str
    agent_name: str
    agent_role: str
    decision: DecisionType
    confidence: float
    reasoning: str
    score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "role": self.agent_role,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "score": self.score,
        }


@dataclass
class ConsensusDecision:
    """Final consensus decision from multiple agents."""
    decision_id: str
    topic: str
    decision: DecisionType
    confidence: ConfidenceLevel
    voting_method: VotingMethod
    opinions: List[AgentOpinion] = field(default_factory=list)
    consensus_score: float = 0.0
    agreement_level: float = 0.0
    dissent_count: int = 0
    summary: str = ""
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    risk_rating: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "topic": self.topic,
            "decision": self.decision.value,
            "confidence": self.confidence.value,
            "voting_method": self.voting_method.value,
            "opinions": [o.to_dict() for o in self.opinions],
            "consensus_score": self.consensus_score,
            "agreement_level": self.agreement_level,
            "dissent_count": self.dissent_count,
            "summary": self.summary,
            "action_items": self.action_items,
            "risk_rating": self.risk_rating,
        }


class ConsensusDecisionEngine:
    """Consensus-based decision engine for multi-agent systems.

    Aggregates opinions from multiple AI agents into a unified decision.
    Combines:
    - Research Score
    - Risk Score
    - Strategy Score
    - Portfolio Score

    Supports multiple voting methods:
    - Majority vote
    - Weighted vote (by agent reputation/confidence)
    - Unanimous consent
    - Supermajority (2/3)
    - Consensus scoring
    """

    def __init__(self):
        self._decisions: List[ConsensusDecision] = []
        self._decision_counter = 0

    def decide(self, opinions: List[AgentOpinion],
               method: VotingMethod = VotingMethod.WEIGHTED) -> ConsensusDecision:
        """Make a consensus decision from agent opinions.

        Args:
            opinions: List of agent opinions.
            method: Voting method to use.

        Returns:
            ConsensusDecision with the final decision.
        """
        self._decision_counter += 1

        if method == VotingMethod.MAJORITY:
            decision, confidence, agreement = self._majority_vote(opinions)
        elif method == VotingMethod.WEIGHTED:
            decision, confidence, agreement = self._weighted_vote(opinions)
        elif method == VotingMethod.UNANIMOUS:
            decision, confidence, agreement = self._unanimous_vote(opinions)
        elif method == VotingMethod.SUPERMAJORITY:
            decision, confidence, agreement = self._supermajority_vote(opinions)
        else:
            decision, confidence, agreement = self._consensus_scoring(opinions)

        dissent = sum(1 for o in opinions if o.decision != decision)

        result = ConsensusDecision(
            decision_id=f"decision_{self._decision_counter}",
            topic=opinions[0].reasoning[:50] if opinions else "no topic",
            decision=decision,
            confidence=confidence,
            voting_method=method,
            opinions=opinions,
            consensus_score=agreement,
            agreement_level=agreement,
            dissent_count=dissent,
            summary=self._generate_summary(decision, confidence, agreement, opinions),
            action_items=self._generate_action_items(decision, opinions),
            risk_rating=self._calculate_risk_rating(opinions),
        )
        self._decisions.append(result)
        return result

    def decide_from_scores(self, research_score: float, risk_score: float,
                           strategy_score: float, portfolio_score: float,
                           topic: str = "") -> ConsensusDecision:
        """Make a decision from numeric scores from different agent domains.

        This is the high-level interface for the investment committee.
        """
        self._decision_counter += 1

        # Create opinions from scores
        opinions = []

        if research_score > 0:
            opinions.append(AgentOpinion(
                agent_id="research", agent_name="Research Agent",
                agent_role="RESEARCH",
                decision=DecisionType.BUY if research_score > 0.6 else DecisionType.HOLD,
                confidence=abs(research_score),
                reasoning=f"Research analysis score: {research_score:.2f}",
                score=research_score,
            ))

        if risk_score > 0:
            risk_decision = DecisionType.HOLD
            if risk_score < 0.3:
                risk_decision = DecisionType.BUY
            elif risk_score > 0.7:
                risk_decision = DecisionType.SELL
            opinions.append(AgentOpinion(
                agent_id="risk", agent_name="Risk Agent",
                agent_role="RISK",
                decision=risk_decision,
                confidence=1 - risk_score,
                reasoning=f"Risk assessment score: {risk_score:.2f}",
                score=risk_score,
            ))

        if strategy_score > 0:
            opinions.append(AgentOpinion(
                agent_id="strategy", agent_name="Strategy Agent",
                agent_role="STRATEGY",
                decision=DecisionType.BUY if strategy_score > 0.5 else DecisionType.HOLD,
                confidence=strategy_score,
                reasoning=f"Strategy signal score: {strategy_score:.2f}",
                score=strategy_score,
            ))

        if portfolio_score > 0:
            opinions.append(AgentOpinion(
                agent_id="portfolio", agent_name="Portfolio Agent",
                agent_role="PORTFOLIO",
                decision=DecisionType.BUY if portfolio_score > 0.5 else DecisionType.HOLD,
                confidence=portfolio_score,
                reasoning=f"Portfolio fit score: {portfolio_score:.2f}",
                score=portfolio_score,
            ))

        return self.decide(opinions, VotingMethod.WEIGHTED)

    def _majority_vote(self, opinions: List[AgentOpinion]) -> Tuple[DecisionType, ConfidenceLevel, float]:
        """Simple majority vote."""
        votes = {}
        for o in opinions:
            votes[o.decision] = votes.get(o.decision, 0) + 1

        winner = max(votes, key=votes.get)
        total = len(opinions)
        agreement = votes[winner] / total

        if agreement >= 0.8:
            confidence = ConfidenceLevel.HIGH
        elif agreement >= 0.6:
            confidence = ConfidenceLevel.MODERATE
        else:
            confidence = ConfidenceLevel.LOW

        return winner, confidence, agreement

    def _weighted_vote(self, opinions: List[AgentOpinion]) -> Tuple[DecisionType, ConfidenceLevel, float]:
        """Weighted vote by agent confidence."""
        scores = {}
        total_weight = 0
        for o in opinions:
            weight = o.confidence
            scores[o.decision] = scores.get(o.decision, 0) + weight
            total_weight += weight

        if total_weight == 0:
            return DecisionType.HOLD, ConfidenceLevel.LOW, 0

        winner = max(scores, key=scores.get)
        agreement = scores[winner] / total_weight

        if agreement >= 0.7:
            confidence = ConfidenceLevel.HIGH
        elif agreement >= 0.5:
            confidence = ConfidenceLevel.MODERATE
        else:
            confidence = ConfidenceLevel.LOW

        return winner, confidence, agreement

    def _unanimous_vote(self, opinions: List[AgentOpinion]) -> Tuple[DecisionType, ConfidenceLevel, float]:
        """Require unanimous consent."""
        decisions = set(o.decision for o in opinions)
        if len(decisions) == 1:
            avg_conf = sum(o.confidence for o in opinions) / len(opinions)
            if avg_conf >= 0.8:
                return list(decisions)[0], ConfidenceLevel.VERY_HIGH, 1.0
            return list(decisions)[0], ConfidenceLevel.HIGH, 1.0
        return DecisionType.HOLD, ConfidenceLevel.LOW, 0.0

    def _supermajority_vote(self, opinions: List[AgentOpinion]) -> Tuple[DecisionType, ConfidenceLevel, float]:
        """Require 2/3 supermajority."""
        votes = {}
        for o in opinions:
            votes[o.decision] = votes.get(o.decision, 0) + 1

        total = len(opinions)
        winner = max(votes, key=votes.get)
        ratio = votes[winner] / total

        if ratio >= 2/3:
            confidence = ConfidenceLevel.HIGH
            return winner, confidence, ratio
        return DecisionType.HOLD, ConfidenceLevel.LOW, ratio

    def _consensus_scoring(self, opinions: List[AgentOpinion]) -> Tuple[DecisionType, ConfidenceLevel, float]:
        """Use a consensus scoring mechanism."""
        # Map decisions to numeric scores
        decision_scores = {
            DecisionType.BUY: 1.0,
            DecisionType.INCREASE: 0.7,
            DecisionType.HOLD: 0.0,
            DecisionType.NO_ACTION: 0.0,
            DecisionType.DECREASE: -0.7,
            DecisionType.SELL: -1.0,
            DecisionType.HEDGE: -0.3,
            DecisionType.EXIT: -1.0,
        }

        total_score = 0
        total_weight = 0
        for o in opinions:
            weight = o.confidence * o.score
            total_score += decision_scores.get(o.decision, 0) * weight
            total_weight += weight

        if total_weight == 0:
            return DecisionType.HOLD, ConfidenceLevel.LOW, 0

        avg_score = total_score / total_weight
        agreement = abs(avg_score)

        if avg_score > 0.5:
            decision = DecisionType.BUY
        elif avg_score > 0.2:
            decision = DecisionType.INCREASE
        elif avg_score < -0.5:
            decision = DecisionType.SELL
        elif avg_score < -0.2:
            decision = DecisionType.DECREASE
        else:
            decision = DecisionType.HOLD

        if agreement > 0.7:
            confidence = ConfidenceLevel.HIGH
        elif agreement > 0.4:
            confidence = ConfidenceLevel.MODERATE
        else:
            confidence = ConfidenceLevel.LOW

        return decision, confidence, agreement

    def _generate_summary(self, decision: DecisionType, confidence: ConfidenceLevel,
                          agreement: float, opinions: List[AgentOpinion]) -> str:
        """Generate a human-readable decision summary."""
        role_names = ", ".join(o.agent_role for o in opinions)
        return (
            f"Consensus decision: {decision.value} "
            f"(confidence: {confidence.value}, agreement: {agreement:.1%}) "
            f"from agents: {role_names}"
        )

    def _generate_action_items(self, decision: DecisionType,
                                opinions: List[AgentOpinion]) -> List[Dict[str, Any]]:
        """Generate actionable items from the decision."""
        items = []
        if decision == DecisionType.BUY:
            items.append({"action": "Place buy order", "priority": "HIGH"})
            items.append({"action": "Set stop-loss", "priority": "HIGH"})
            items.append({"action": "Monitor position", "priority": "MEDIUM"})
        elif decision == DecisionType.SELL:
            items.append({"action": "Place sell order", "priority": "HIGH"})
            items.append({"action": "Review portfolio allocation", "priority": "MEDIUM"})
        elif decision == DecisionType.HOLD:
            items.append({"action": "Maintain current position", "priority": "LOW"})
            items.append({"action": "Set review date", "priority": "MEDIUM"})
        elif decision == DecisionType.HEDGE:
            items.append({"action": "Set up hedge position", "priority": "HIGH"})
            items.append({"action": "Monitor hedge effectiveness", "priority": "HIGH"})
        return items

    def _calculate_risk_rating(self, opinions: List[AgentOpinion]) -> str:
        """Calculate overall risk rating from opinions."""
        risk_opinions = [o for o in opinions if o.agent_role == "RISK"]
        if risk_opinions:
            avg_risk = sum(o.score for o in risk_opinions) / len(risk_opinions)
            if avg_risk < 0.3:
                return "LOW"
            elif avg_risk < 0.6:
                return "MEDIUM"
            else:
                return "HIGH"
        return "UNKNOWN"

    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get history of all consensus decisions."""
        return [d.to_dict() for d in self._decisions]

    def get_agreement_metrics(self) -> Dict[str, Any]:
        """Get metrics on inter-agent agreement."""
        if not self._decisions:
            return {"total_decisions": 0}
        avg_agreement = sum(d.agreement_level for d in self._decisions) / len(self._decisions)
        avg_dissent = sum(d.dissent_count for d in self._decisions) / len(self._decisions)
        return {
            "total_decisions": len(self._decisions),
            "avg_agreement": avg_agreement,
            "avg_dissent": avg_dissent,
            "high_confidence_count": sum(1 for d in self._decisions
                                         if d.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH)),
        }
