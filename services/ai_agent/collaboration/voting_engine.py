"""Voting Engine — multi-agent voting with majority, weighted, and confidence-based strategies.

Pipeline:
    Vote (agent opinion with weight + confidence)
        -> VotingEngine.cast_vote() (record individual vote)
        -> VotingEngine.tally() (aggregate votes by strategy)
        -> VotingResult (winning option, margin, agreement level)

Supports multiple voting strategies for different decision-making scenarios
in the multi-agent system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class VotingStrategy(str, Enum):
    """Strategy for aggregating votes."""
    MAJORITY = "majority"           # Simple majority (>50%)
    WEIGHTED = "weighted"           # Weighted by agent priority/confidence
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # Weighted by confidence score
    UNANIMOUS = "unanimous"         # All must agree
    SUPER_MAJORITY = "super_majority"  # >= 2/3 majority
    EXPERT_PRIORITY = "expert_priority"  # Expert agent vote counts more


@dataclass
class Vote:
    """A single vote cast by an agent.

    Attributes:
        vote_id: Unique vote identifier.
        agent_id: Voting agent's ID.
        option: The option being voted for.
        weight: Vote weight (default 1.0, higher = more influential).
        confidence: Agent's confidence in this vote (0.0 - 1.0).
        rationale: Human-readable reason for the vote.
        metadata: Additional vote metadata.
    """

    vote_id: str = field(default_factory=lambda: uuid4().hex)
    agent_id: str = ""
    option: str = ""
    weight: float = 1.0
    confidence: float = 0.5
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def effective_weight(self) -> float:
        """Return the effective weight combining base weight and confidence."""
        return self.weight * self.confidence


@dataclass
class VotingResult:
    """Result of a voting round.

    Attributes:
        result_id: Unique result identifier.
        strategy: Voting strategy used.
        winning_option: The option with the most support.
        scores: Score breakdown per option.
        total_votes: Number of votes cast.
        agreement_level: 0.0 (full disagreement) to 1.0 (full agreement).
        is_decisive: Whether the result meets the strategy threshold.
        details: Additional result details.
    """

    result_id: str = field(default_factory=lambda: uuid4().hex)
    strategy: VotingStrategy = VotingStrategy.MAJORITY
    winning_option: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    total_votes: int = 0
    agreement_level: float = 0.0
    is_decisive: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return voting result as a dictionary."""
        return {
            "result_id": self.result_id,
            "strategy": self.strategy.value,
            "winning_option": self.winning_option,
            "scores": self.scores,
            "total_votes": self.total_votes,
            "agreement_level": self.agreement_level,
            "is_decisive": self.is_decisive,
        }


class VotingEngine:
    """Multi-agent voting engine with configurable aggregation strategies.

    Collects votes from agents and aggregates them using the specified
    strategy. Supports majority, weighted, confidence-weighted, unanimous,
    super-majority, and expert-priority voting.

    Supports:
        - Multiple voting strategies
        - Weighted voting (agent priority + confidence)
        - Majority / Super-majority thresholds
        - Unanimous requirement
        - Expert priority override
        - Agreement level measurement
        - Decisiveness check

    Usage:
        engine = VotingEngine()
        await engine.initialize()
        await engine.cast_vote(Vote(agent_id="a1", option="buy", weight=1.0))
        result = await engine.tally(VotingStrategy.WEIGHTED)
    """

    def __init__(self) -> None:
        """Initialize the voting engine."""
        self._votes: List[Vote] = []
        self._initialized: bool = False
        logger.info("VotingEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the voting engine."""
        if self._initialized:
            logger.warning("VotingEngine already initialized")
            return
        self._initialized = True
        logger.info("VotingEngine initialized")

    async def shutdown(self) -> None:
        """Shut down the voting engine."""
        if not self._initialized:
            return
        self._votes.clear()
        self._initialized = False
        logger.info("VotingEngine shutdown complete")

    # ── Vote Casting ──

    async def cast_vote(self, vote: Vote) -> None:
        """Record a vote from an agent.

        Args:
            vote: The vote to record.
        """
        if not self._initialized:
            raise RuntimeError("VotingEngine not initialized")
        self._votes.append(vote)
        logger.debug("Vote cast: agent=%s, option=%s, weight=%.2f, confidence=%.2f",
                     vote.agent_id, vote.option, vote.weight, vote.confidence)

    async def cast_votes(self, votes: List[Vote]) -> None:
        """Record multiple votes.

        Args:
            votes: List of votes to record.
        """
        for vote in votes:
            await self.cast_vote(vote)

    # ── Tallying ──

    async def tally(self, strategy: VotingStrategy = VotingStrategy.MAJORITY) -> VotingResult:
        """Aggregate votes using the specified strategy.

        Args:
            strategy: Voting strategy to apply.

        Returns:
            VotingResult with winning option and scores.
        """
        if not self._initialized:
            raise RuntimeError("VotingEngine not initialized")

        if not self._votes:
            return VotingResult(
                strategy=strategy,
                winning_option="",
                total_votes=0,
                is_decisive=False,
                details={"reason": "No votes cast"},
            )

        if strategy == VotingStrategy.MAJORITY:
            result = self._tally_majority()
        elif strategy == VotingStrategy.WEIGHTED:
            result = self._tally_weighted()
        elif strategy == VotingStrategy.CONFIDENCE_WEIGHTED:
            result = self._tally_confidence_weighted()
        elif strategy == VotingStrategy.UNANIMOUS:
            result = self._tally_unanimous()
        elif strategy == VotingStrategy.SUPER_MAJORITY:
            result = self._tally_super_majority()
        elif strategy == VotingStrategy.EXPERT_PRIORITY:
            result = self._tally_expert_priority()
        else:
            result = self._tally_majority()

        result.strategy = strategy
        result.total_votes = len(self._votes)
        logger.info("Voting result: winner=%s, strategy=%s, decisive=%s",
                    result.winning_option, strategy.value, result.is_decisive)
        return result

    def _tally_majority(self) -> VotingResult:
        """Simple majority: option with most votes wins.

        Returns:
            VotingResult.
        """
        counts: Dict[str, int] = {}
        for vote in self._votes:
            counts[vote.option] = counts.get(vote.option, 0) + 1

        total = len(self._votes)
        scores = {opt: count / total for opt, count in counts.items()}
        winner = max(counts, key=counts.get)
        is_decisive = counts[winner] > total / 2

        return VotingResult(
            winning_option=winner,
            scores=scores,
            agreement_level=counts[winner] / total,
            is_decisive=is_decisive,
        )

    def _tally_weighted(self) -> VotingResult:
        """Weighted voting by agent weight.

        Returns:
            VotingResult.
        """
        scores: Dict[str, float] = {}
        total_weight = 0.0

        for vote in self._votes:
            scores[vote.option] = scores.get(vote.option, 0.0) + vote.weight
            total_weight += vote.weight

        if total_weight == 0:
            return VotingResult(winning_option="", is_decisive=False)

        normalized = {opt: s / total_weight for opt, s in scores.items()}
        winner = max(scores, key=scores.get)
        is_decisive = scores[winner] > total_weight / 2

        return VotingResult(
            winning_option=winner,
            scores=normalized,
            agreement_level=scores[winner] / total_weight,
            is_decisive=is_decisive,
        )

    def _tally_confidence_weighted(self) -> VotingResult:
        """Voting weighted by agent confidence.

        Returns:
            VotingResult.
        """
        scores: Dict[str, float] = {}
        total_confidence = 0.0

        for vote in self._votes:
            effective = vote.effective_weight
            scores[vote.option] = scores.get(vote.option, 0.0) + effective
            total_confidence += effective

        if total_confidence == 0:
            return VotingResult(winning_option="", is_decisive=False)

        normalized = {opt: s / total_confidence for opt, s in scores.items()}
        winner = max(scores, key=scores.get)

        return VotingResult(
            winning_option=winner,
            scores=normalized,
            agreement_level=scores[winner] / total_confidence,
            is_decisive=True,
        )

    def _tally_unanimous(self) -> VotingResult:
        """Unanimous voting: all must agree on same option.

        Returns:
            VotingResult.
        """
        options = {v.option for v in self._votes}
        is_unanimous = len(options) == 1
        winner = next(iter(options)) if is_unanimous else ""

        scores: Dict[str, float] = {}
        for vote in self._votes:
            scores[vote.option] = scores.get(vote.option, 0.0) + 1.0
        total = len(self._votes)
        normalized = {opt: s / total for opt, s in scores.items()}

        return VotingResult(
            winning_option=winner,
            scores=normalized,
            agreement_level=1.0 if is_unanimous else 0.0,
            is_decisive=is_unanimous,
        )

    def _tally_super_majority(self) -> VotingResult:
        """Super-majority voting: >= 2/3 threshold.

        Returns:
            VotingResult.
        """
        result = self._tally_majority()
        threshold = 2.0 / 3.0
        result.is_decisive = result.agreement_level >= threshold
        if not result.is_decisive:
            result.winning_option = ""
        return result

    def _tally_expert_priority(self) -> VotingResult:
        """Expert priority: highest-weighted agent's vote wins.

        Returns:
            VotingResult.
        """
        if not self._votes:
            return VotingResult(is_decisive=False)

        expert_vote = max(self._votes, key=lambda v: v.weight)

        scores: Dict[str, float] = {}
        for vote in self._votes:
            scores[vote.option] = scores.get(vote.option, 0.0) + vote.weight
        total = sum(scores.values())
        normalized = {opt: s / total for opt, s in scores.items()}

        return VotingResult(
            winning_option=expert_vote.option,
            scores=normalized,
            agreement_level=expert_vote.weight / total,
            is_decisive=True,
            details={"expert_agent": expert_vote.agent_id},
        )

    # ── Reset ──

    def reset(self) -> None:
        """Clear all votes for a new round."""
        self._votes.clear()
        logger.debug("Votes reset")

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the voting engine state.

        Returns:
            Dict with vote count.
        """
        return {
            "initialized": self._initialized,
            "votes_cast": len(self._votes),
        }
