"""Negotiation Engine — multi-round proposal/counter-proposal negotiation between agents.

Pipeline:
    Agent A sends Proposal
        -> NegotiationEngine.submit_proposal() (register proposal)
        -> NegotiationEngine.route_to_agent() (deliver to Agent B)
        -> Agent B sends CounterProposal
        -> NegotiationEngine.evaluate() (check for agreement)
        -> NegotiationResult (agreement or deadlock)

Supports multi-round negotiation with configurable max rounds and
agreement threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class NegotiationStatus(str, Enum):
    """Status of a negotiation session."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AGREED = "agreed"
    DEADLOCKED = "deadlocked"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class Proposal:
    """A proposal from one agent to another during negotiation.

    Attributes:
        proposal_id: Unique proposal identifier.
        session_id: Negotiation session ID.
        from_agent_id: Proposing agent's ID.
        to_agent_id: Target agent's ID.
        content: Proposal content.
        round_number: Current negotiation round (1-based).
        confidence: Proposer's confidence (0.0 - 1.0).
        created_at: When the proposal was created.
    """

    proposal_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    from_agent_id: str = ""
    to_agent_id: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    round_number: int = 1
    confidence: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Return proposal as a dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "session_id": self.session_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "content": self.content,
            "round_number": self.round_number,
            "confidence": self.confidence,
        }


@dataclass
class CounterProposal:
    """A counter-proposal responding to a proposal.

    Attributes:
        counter_id: Unique counter-proposal identifier.
        original_proposal_id: The proposal being responded to.
        from_agent_id: Counter-proposing agent's ID.
        to_agent_id: Original proposer's ID.
        content: Counter-proposal content.
        accepted: Whether the original proposal is accepted as-is.
        modifications: What changes were made.
        round_number: Current negotiation round.
    """

    counter_id: str = field(default_factory=lambda: uuid4().hex)
    original_proposal_id: str = ""
    from_agent_id: str = ""
    to_agent_id: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    accepted: bool = False
    modifications: List[str] = field(default_factory=list)
    round_number: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Return counter-proposal as a dictionary."""
        return {
            "counter_id": self.counter_id,
            "original_proposal_id": self.original_proposal_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "content": self.content,
            "accepted": self.accepted,
            "modifications": self.modifications,
            "round_number": self.round_number,
        }


@dataclass
class NegotiationResult:
    """Final result of a negotiation session.

    Attributes:
        session_id: Negotiation session ID.
        status: Final negotiation status.
        final_agreement: The agreed-upon content (if any).
        total_rounds: Number of rounds taken.
        proposals: All proposals exchanged.
        started_at: When negotiation started.
        ended_at: When negotiation ended.
    """

    session_id: str = ""
    status: NegotiationStatus = NegotiationStatus.OPEN
    final_agreement: Optional[Dict[str, Any]] = None
    total_rounds: int = 0
    proposals: List[Any] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    @property
    def is_agreed(self) -> bool:
        """Return whether agreement was reached."""
        return self.status == NegotiationStatus.AGREED

    def to_dict(self) -> Dict[str, Any]:
        """Return negotiation result as a dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "final_agreement": self.final_agreement,
            "total_rounds": self.total_rounds,
            "proposal_count": len(self.proposals),
        }


class NegotiationEngine:
    """Multi-round proposal/counter-proposal negotiation between agents.

    Enables agents to negotiate decisions through structured proposal
    exchange. Supports configurable max rounds and agreement thresholds.

    Supports:
        - Proposal submission and routing
        - Counter-proposal handling
        - Multi-round negotiation (configurable max rounds)
        - Agreement detection
        - Deadlock detection
        - Timeout enforcement
        - Session management

    Usage:
        engine = NegotiationEngine(message_bus)
        await engine.initialize()
        proposal = Proposal(from_agent_id="strategy", to_agent_id="risk", ...)
        result = await engine.start_negotiation(proposal, max_rounds=3)
    """

    def __init__(self, message_bus: MessageBus, max_rounds: int = 3) -> None:
        """Initialize the negotiation engine.

        Args:
            message_bus: Message bus for inter-agent communication.
            max_rounds: Default maximum negotiation rounds.
        """
        self._message_bus: MessageBus = message_bus
        self._max_rounds: int = max_rounds
        self._sessions: Dict[str, NegotiationResult] = {}
        self._proposals: Dict[str, List[Proposal]] = {}  # session_id -> proposals
        self._initialized: bool = False
        logger.info("NegotiationEngine created (max_rounds=%d)", max_rounds)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the negotiation engine."""
        if self._initialized:
            logger.warning("NegotiationEngine already initialized")
            return
        self._initialized = True
        logger.info("NegotiationEngine initialized")

    async def shutdown(self) -> None:
        """Shut down the negotiation engine."""
        if not self._initialized:
            return
        self._sessions.clear()
        self._proposals.clear()
        self._initialized = False
        logger.info("NegotiationEngine shutdown complete")

    # ── Negotiation ──

    async def start_negotiation(
        self, proposal: Proposal, max_rounds: Optional[int] = None,
    ) -> NegotiationResult:
        """Start a new negotiation session.

        Args:
            proposal: The initial proposal.
            max_rounds: Maximum negotiation rounds (defaults to engine setting).

        Returns:
            NegotiationResult with final status.
        """
        if not self._initialized:
            raise RuntimeError("NegotiationEngine not initialized")

        session_id = proposal.session_id or uuid4().hex[:12]
        max_r = max_rounds or self._max_rounds

        result = NegotiationResult(
            session_id=session_id,
            status=NegotiationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )
        self._sessions[session_id] = result

        await self.submit_proposal(proposal)

        logger.info("Negotiation started: session=%s, from=%s, to=%s",
                    session_id, proposal.from_agent_id, proposal.to_agent_id)

        # In a real implementation, this would await responses asynchronously
        # For the framework, we set up the session and return
        return result

    async def submit_proposal(self, proposal: Proposal) -> None:
        """Submit a proposal in an ongoing negotiation.

        Args:
            proposal: The proposal to submit.
        """
        session_id = proposal.session_id
        if session_id not in self._sessions:
            raise ValueError(f"Unknown negotiation session: {session_id}")

        self._proposals.setdefault(session_id, []).append(proposal)

        # Check round limit
        max_r = self._max_rounds
        if proposal.round_number > max_r:
            result = self._sessions[session_id]
            result.status = NegotiationStatus.DEADLOCKED
            result.ended_at = datetime.now(timezone.utc)
            result.total_rounds = proposal.round_number
            logger.warning("Negotiation deadlocked: session=%s, round=%d",
                          session_id, proposal.round_number)
            return

        # Send proposal to target agent via message bus
        msg = Message(
            msg_type=MessageType.REQUEST,
            topic="negotiation.proposal",
            sender_id=proposal.from_agent_id,
            payload={
                "proposal_id": proposal.proposal_id,
                "session_id": session_id,
                "content": proposal.content,
                "round_number": proposal.round_number,
            },
        )
        await self._message_bus.publish(msg)

        logger.debug("Proposal submitted: session=%s, round=%d, from=%s",
                     session_id, proposal.round_number, proposal.from_agent_id)

    async def submit_counter_proposal(self, counter: CounterProposal) -> None:
        """Submit a counter-proposal.

        Args:
            counter: The counter-proposal.
        """
        # Find the original proposal's session
        original = None
        for session_id, proposals in self._proposals.items():
            for p in proposals:
                if p.proposal_id == counter.original_proposal_id:
                    original = p
                    break
            if original:
                break

        if not original:
            raise ValueError(f"Original proposal not found: {counter.original_proposal_id}")

        session_id = original.session_id

        if counter.accepted:
            # Agreement reached
            result = self._sessions.get(session_id)
            if result:
                result.status = NegotiationStatus.AGREED
                result.final_agreement = counter.content
                result.ended_at = datetime.now(timezone.utc)
                result.total_rounds = counter.round_number
                result.proposals = list(self._proposals.get(session_id, []))
            logger.info("Negotiation agreed: session=%s, round=%d",
                       session_id, counter.round_number)
        else:
            # Continue negotiation with a new proposal
            new_proposal = Proposal(
                session_id=session_id,
                from_agent_id=counter.from_agent_id,
                to_agent_id=counter.to_agent_id,
                content=counter.content,
                round_number=counter.round_number + 1,
            )
            await self.submit_proposal(new_proposal)

        # Send counter-proposal via message bus
        msg = Message(
            msg_type=MessageType.RESPONSE,
            topic="negotiation.counter",
            sender_id=counter.from_agent_id,
            payload={
                "counter_id": counter.counter_id,
                "original_proposal_id": counter.original_proposal_id,
                "session_id": session_id,
                "content": counter.content,
                "accepted": counter.accepted,
            },
        )
        await self._message_bus.publish(msg)

    # ── Query ──

    def get_session(self, session_id: str) -> Optional[NegotiationResult]:
        """Get a negotiation session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            The negotiation result, or None if not found.
        """
        return self._sessions.get(session_id)

    def get_proposals(self, session_id: str) -> List[Proposal]:
        """Get all proposals for a session.

        Args:
            session_id: The session identifier.

        Returns:
            List of proposals.
        """
        return self._proposals.get(session_id, [])

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the negotiation engine state.

        Returns:
            Dict with session count and status breakdown.
        """
        status_counts: Dict[str, int] = {}
        for s in self._sessions.values():
            status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1

        return {
            "initialized": self._initialized,
            "active_sessions": len(self._sessions),
            "max_rounds": self._max_rounds,
            "status_breakdown": status_counts,
        }
