"""Consensus Engine — unified multi-agent consensus reaching with voting, conflict resolution, and negotiation.

Pipeline:
    ConsensusProposal (topic + options from agents)
        -> ConsensusEngine.reach_consensus()
        -> VotingEngine.tally() (aggregate agent votes)
        -> ConflictResolver.resolve() (handle disagreements)
        -> NegotiationEngine.start_negotiation() (if needed)
        -> ConsensusResult (final decision + agreement level)

The Consensus Engine is the central decision-making component that combines
voting, conflict resolution, and negotiation to reach a unified decision
from multiple agent opinions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.voting_engine import (
    VotingEngine,
    Vote,
    VotingStrategy,
    VotingResult,
)
from services.ai_agent.collaboration.conflict_resolver import (
    ConflictResolver,
    Conflict,
    ConflictType,
    ResolutionStrategy as ConflictResolutionStrategy,
    Resolution,
)
from services.ai_agent.collaboration.negotiation_engine import (
    NegotiationEngine,
    Proposal,
    NegotiationResult,
    NegotiationStatus,
)

logger = logging.getLogger(__name__)


class ConsensusStatus(str, Enum):
    """Status of a consensus-reaching process."""
    INITIATED = "initiated"
    VOTING = "voting"
    RESOLVING_CONFLICTS = "resolving_conflicts"
    NEGOTIATING = "negotiating"
    REACHED = "reached"
    FAILED = "failed"
    DEADLOCKED = "deadlocked"


@dataclass
class ConsensusProposal:
    """A proposal submitted for multi-agent consensus.

    Attributes:
        proposal_id: Unique proposal identifier.
        topic: The decision topic.
        options: List of possible options/decisions.
        agent_opinions: Mapping of agent_id -> preferred option.
        agent_confidences: Mapping of agent_id -> confidence score.
        metadata: Additional context.
    """

    proposal_id: str = field(default_factory=lambda: uuid4().hex)
    topic: str = ""
    options: List[Any] = field(default_factory=list)
    agent_opinions: Dict[str, Any] = field(default_factory=dict)
    agent_confidences: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return proposal as a dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "topic": self.topic,
            "options": self.options,
            "agent_count": len(self.agent_opinions),
        }


@dataclass
class ConsensusResult:
    """Result of a consensus-reaching process.

    Attributes:
        consensus_id: Unique consensus identifier.
        proposal_id: The original proposal ID.
        status: Final consensus status.
        decision: The agreed-upon decision.
        agreement_level: 0.0 (full disagreement) to 1.0 (full agreement).
        voting_result: Raw voting result.
        conflicts_resolved: Conflicts that were resolved.
        duration_ms: Time taken to reach consensus.
        rationale: Human-readable explanation.
    """

    consensus_id: str = field(default_factory=lambda: uuid4().hex)
    proposal_id: str = ""
    status: ConsensusStatus = ConsensusStatus.INITIATED
    decision: Any = None
    agreement_level: float = 0.0
    voting_result: Optional[VotingResult] = None
    conflicts_resolved: List[Resolution] = field(default_factory=list)
    duration_ms: float = 0.0
    rationale: str = ""

    @property
    def is_reached(self) -> bool:
        """Return whether consensus was reached."""
        return self.status == ConsensusStatus.REACHED

    def to_dict(self) -> Dict[str, Any]:
        """Return consensus result as a dictionary."""
        return {
            "consensus_id": self.consensus_id,
            "proposal_id": self.proposal_id,
            "status": self.status.value,
            "decision": str(self.decision)[:200] if self.decision else None,
            "agreement_level": self.agreement_level,
            "conflicts_resolved": len(self.conflicts_resolved),
            "duration_ms": self.duration_ms,
            "rationale": self.rationale,
        }


class ConsensusEngine:
    """Central engine for reaching multi-agent consensus.

    Orchestrates the consensus process through three phases:
    1. Voting — collect and aggregate agent opinions
    2. Conflict Resolution — resolve disagreements
    3. Negotiation — if needed, negotiate between agents

    Supports:
        - Multi-phase consensus (voting → conflict resolution → negotiation)
        - Configurable voting strategies
        - Automatic conflict detection and resolution
        - Negotiation fallback for unresolved disagreements
        - Agreement level measurement
        - Duration tracking

    Usage:
        engine = ConsensusEngine(voting, conflict_resolver, negotiation)
        await engine.initialize()
        proposal = ConsensusProposal(topic="Should we buy?", ...)
        result = await engine.reach_consensus(proposal)
    """

    def __init__(
        self,
        voting_engine: VotingEngine,
        conflict_resolver: ConflictResolver,
        negotiation_engine: NegotiationEngine,
    ) -> None:
        """Initialize the consensus engine.

        Args:
            voting_engine: Voting engine for opinion aggregation.
            conflict_resolver: Conflict resolver for disagreement handling.
            negotiation_engine: Negotiation engine for multi-round discussion.
        """
        self._voting: VotingEngine = voting_engine
        self._conflict_resolver: ConflictResolver = conflict_resolver
        self._negotiation: NegotiationEngine = negotiation_engine
        self._results: Dict[str, ConsensusResult] = {}
        self._initialized: bool = False
        logger.info("ConsensusEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the consensus engine."""
        if self._initialized:
            logger.warning("ConsensusEngine already initialized")
            return
        self._initialized = True
        logger.info("ConsensusEngine initialized")

    async def shutdown(self) -> None:
        """Shut down the consensus engine."""
        if not self._initialized:
            return
        self._results.clear()
        self._initialized = False
        logger.info("ConsensusEngine shutdown complete")

    # ── Consensus ──

    async def reach_consensus(
        self,
        proposal: ConsensusProposal,
        voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED,
    ) -> ConsensusResult:
        """Reach consensus on a proposal through voting, conflict resolution, and negotiation.

        Args:
            proposal: The proposal to reach consensus on.
            voting_strategy: Strategy for aggregating votes.

        Returns:
            ConsensusResult with final decision.
        """
        if not self._initialized:
            raise RuntimeError("ConsensusEngine not initialized")

        started_at = time.monotonic()
        logger.info("Reaching consensus on: %s (agents=%d)",
                    proposal.topic, len(proposal.agent_opinions))

        result = ConsensusResult(
            proposal_id=proposal.proposal_id,
            status=ConsensusStatus.INITIATED,
        )

        # Phase 1: Voting
        result.status = ConsensusStatus.VOTING
        await self._voting.reset()

        for agent_id, opinion in proposal.agent_opinions.items():
            confidence = proposal.agent_confidences.get(agent_id, 0.5)
            vote = Vote(
                agent_id=agent_id,
                option=str(opinion),
                confidence=confidence,
                rationale=f"Agent opinion on: {proposal.topic}",
            )
            await self._voting.cast_vote(vote)

        voting_result = await self._voting.tally(voting_strategy)
        result.voting_result = voting_result

        if voting_result.is_decisive:
            # Consensus reached through voting
            result.status = ConsensusStatus.REACHED
            result.decision = voting_result.winning_option
            result.agreement_level = voting_result.agreement_level
            result.rationale = (
                f"Consensus reached via {voting_strategy.value} voting: "
                f"'{voting_result.winning_option}' with "
                f"{voting_result.agreement_level:.0%} agreement"
            )
        else:
            # Phase 2: Conflict Resolution
            result.status = ConsensusStatus.RESOLVING_CONFLICTS
            conflicts = self._detect_conflicts(proposal)

            for conflict in conflicts:
                resolution = await self._conflict_resolver.resolve(
                    conflict,
                    strategy=ConflictResolutionStrategy.RULE_BASED,
                    agent_confidences=proposal.agent_confidences,
                )
                result.conflicts_resolved.append(resolution)

            if result.conflicts_resolved:
                # Use the resolution from the first conflict
                final_resolution = result.conflicts_resolved[0]
                result.status = ConsensusStatus.REACHED
                result.decision = final_resolution.final_decision
                result.agreement_level = 0.6  # Partial agreement through resolution
                result.rationale = final_resolution.rationale
            else:
                # Phase 3: Negotiation (fallback)
                result.status = ConsensusStatus.NEGOTIATING
                # Start a negotiation between disagreeing agents
                agent_ids = list(proposal.agent_opinions.keys())
                if len(agent_ids) >= 2:
                    neg_proposal = Proposal(
                        from_agent_id=agent_ids[0],
                        to_agent_id=agent_ids[1],
                        content={"topic": proposal.topic, "options": proposal.options},
                    )
                    neg_result = await self._negotiation.start_negotiation(
                        neg_proposal, max_rounds=3,
                    )
                    if neg_result.is_agreed:
                        result.status = ConsensusStatus.REACHED
                        result.decision = neg_result.final_agreement
                        result.agreement_level = 0.5
                        result.rationale = "Consensus reached through negotiation"
                    else:
                        result.status = ConsensusStatus.DEADLOCKED
                        result.rationale = "Consensus deadlocked after negotiation"
                else:
                    result.status = ConsensusStatus.FAILED
                    result.rationale = "Insufficient agents for negotiation"

        result.duration_ms = (time.monotonic() - started_at) * 1000
        self._results[result.consensus_id] = result

        logger.info("Consensus %s: status=%s, decision=%s, duration=%.0fms",
                    result.consensus_id[:8], result.status.value,
                    result.decision, result.duration_ms)
        return result

    # ── Conflict Detection ──

    def _detect_conflicts(self, proposal: ConsensusProposal) -> List[Conflict]:
        """Detect conflicts between agent opinions in a proposal.

        Args:
            proposal: The consensus proposal.

        Returns:
            List of detected conflicts.
        """
        conflicts: List[Conflict] = []
        agent_ids = list(proposal.agent_opinions.keys())

        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                a_id = agent_ids[i]
                b_id = agent_ids[j]
                a_pos = proposal.agent_opinions[a_id]
                b_pos = proposal.agent_opinions[b_id]

                conflict = self._conflict_resolver.detect(
                    agent_a_id=a_id,
                    position_a=a_pos,
                    agent_b_id=b_id,
                    position_b=b_pos,
                )
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    # ── Quick Consensus ──

    async def quick_consensus(
        self, topic: str, opinions: Dict[str, Any],
    ) -> ConsensusResult:
        """Quick consensus with default settings.

        Args:
            topic: Decision topic.
            opinions: Agent opinions (agent_id -> opinion).

        Returns:
            ConsensusResult.
        """
        proposal = ConsensusProposal(
            topic=topic,
            agent_opinions=opinions,
            agent_confidences={aid: 0.5 for aid in opinions},
            options=list(set(str(v) for v in opinions.values())),
        )
        return await self.reach_consensus(proposal)

    # ── Query ──

    def get_result(self, consensus_id: str) -> Optional[ConsensusResult]:
        """Get a consensus result by ID.

        Args:
            consensus_id: The consensus identifier.

        Returns:
            The result, or None if not found.
        """
        return self._results.get(consensus_id)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the consensus engine state.

        Returns:
            Dict with result count and status breakdown.
        """
        status_counts: Dict[str, int] = {}
        for r in self._results.values():
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

        return {
            "initialized": self._initialized,
            "total_results": len(self._results),
            "status_breakdown": status_counts,
        }
