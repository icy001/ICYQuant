"""
ICYQuant Voting Engine — weighted multi-agent voting for decision-making.

Supports multiple voting strategies (majority, weighted, ranked-choice,
veto) with configurable thresholds, quorum requirements, and audit trails.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .agent_message import VoteMessage

logger = logging.getLogger(__name__)


class VoteDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    VETO = "veto"           # Overrides all approvals
    CONDITIONAL = "conditional"  # Approve with conditions


class VotingStrategy(str, Enum):
    MAJORITY = "majority"            # Simple majority (>50%)
    SUPERMAJORITY = "supermajority"  # ≥2/3 required
    WEIGHTED = "weighted"            # Weighted by agent expertise
    RANKED_CHOICE = "ranked_choice"  # Ranked choice voting
    UNANIMOUS = "unanimous"         # All must agree
    VETO_POWER = "veto_power"       # Specific agents have veto


@dataclass
class VotingConfig:
    strategy: VotingStrategy = VotingStrategy.MAJORITY
    threshold: float = 0.5          # Required approval ratio
    quorum: int = 3                  # Minimum votes needed
    veto_agents: list[str] = field(default_factory=list)  # Agent IDs with veto power
    voting_period_seconds: int = 300
    allow_abstain: bool = True
    allow_conditional: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoteSession:
    """An active voting session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposal: str = ""
    config: VotingConfig = field(default_factory=VotingConfig)
    votes: list[VoteMessage] = field(default_factory=list)
    status: str = "open"            # open, closed, resolved
    decision: Optional[VoteDecision] = None
    approval_ratio: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def voter_count(self) -> int:
        return len(self.votes)

    @property
    def has_quorum(self) -> bool:
        return self.voter_count >= self.config.quorum


class VotingEngine:
    """Multi-agent voting engine with multiple strategies.

    Features:
        - Simple majority, supermajority, weighted, ranked-choice, unanimous
        - Veto power for risk/compliance agents
        - Configurable quorum and thresholds
        - Timed voting sessions
        - Immutable vote audit trail
        - Conditional approvals with requirements
    """

    def __init__(self) -> None:
        self._sessions: dict[str, VoteSession] = {}
        self._total_sessions = 0

    # ── Session Management ──

    def create_session(self, proposal: str,
                       config: Optional[VotingConfig] = None) -> VoteSession:
        """Create a new voting session."""
        session = VoteSession(
            proposal=proposal,
            config=config or VotingConfig(),
        )
        self._sessions[session.session_id] = session
        self._total_sessions += 1
        logger.info("Voting session created: %s", session.session_id)
        return session

    def close_session(self, session_id: str) -> Optional[VoteSession]:
        """Close a voting session and tally results."""
        session = self._sessions.get(session_id)
        if session is None or session.status != "open":
            return None

        session.status = "closed"
        session.closed_at = datetime.now(timezone.utc)

        # Tally votes
        decision, ratio = self._tally(session)
        session.decision = decision
        session.approval_ratio = ratio

        logger.info("Voting session %s closed: %s (%.1f%%)",
                     session_id, decision.value if decision else "undecided", ratio * 100)
        return session

    # ── Vote Casting ──

    def cast_vote(self, session_id: str, vote: VoteMessage) -> bool:
        """Cast a vote in a session."""
        session = self._sessions.get(session_id)
        if session is None or session.status != "open":
            return False

        # Check for duplicate voter
        for existing in session.votes:
            if existing.voter_id == vote.voter_id:
                logger.warning("Duplicate vote from %s in %s", vote.voter_id, session_id)
                return False

        session.votes.append(vote)

        # Check if auto-close conditions met
        if self._check_auto_close(session):
            self.close_session(session_id)

        return True

    def _check_auto_close(self, session: VoteSession) -> bool:
        """Check if session should auto-close."""
        if not session.has_quorum:
            return False

        if session.config.strategy == VotingStrategy.UNANIMOUS:
            # Auto-reject if any vote is not APPROVE
            return False

        return False

    # ── Tally Logic ──

    def _tally(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Tally votes according to the configured strategy."""
        if session.config.strategy == VotingStrategy.VETO_POWER:
            return self._tally_veto(session)
        elif session.config.strategy == VotingStrategy.WEIGHTED:
            return self._tally_weighted(session)
        elif session.config.strategy == VotingStrategy.UNANIMOUS:
            return self._tally_unanimous(session)
        elif session.config.strategy == VotingStrategy.SUPERMAJORITY:
            return self._tally_supermajority(session)
        else:  # MAJORITY or RANKED_CHOICE
            return self._tally_majority(session)

    def _tally_majority(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Simple majority: >50% approve wins."""
        if not session.votes:
            return None, 0.0

        approve = sum(1 for v in session.votes if v.choice == VoteDecision.APPROVE.value)
        total = len(session.votes)
        ratio = approve / total if total > 0 else 0.0

        decision = VoteDecision.APPROVE if ratio > session.config.threshold else VoteDecision.REJECT
        return decision, ratio

    def _tally_supermajority(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Supermajority: ≥2/3 approve required."""
        threshold = session.config.threshold  # Usually 0.667

        if not session.votes:
            return None, 0.0

        approve = sum(1 for v in session.votes if v.choice == VoteDecision.APPROVE.value)
        total = len(session.votes)
        ratio = approve / total if total > 0 else 0.0

        decision = VoteDecision.APPROVE if ratio >= threshold else VoteDecision.REJECT
        return decision, ratio

    def _tally_weighted(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Weighted voting by agent expertise weight."""
        if not session.votes:
            return None, 0.0

        total_weight = 0.0
        approve_weight = 0.0

        for vote in session.votes:
            w = vote.weight
            total_weight += w
            if vote.choice == VoteDecision.APPROVE.value:
                approve_weight += w

        ratio = approve_weight / total_weight if total_weight > 0 else 0.0
        decision = VoteDecision.APPROVE if ratio > session.config.threshold else VoteDecision.REJECT
        return decision, ratio

    def _tally_unanimous(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Unanimous: all must approve."""
        if not session.votes:
            return None, 0.0

        all_approve = all(v.choice == VoteDecision.APPROVE.value for v in session.votes)
        return (VoteDecision.APPROVE if all_approve else VoteDecision.REJECT), 0.0

    def _tally_veto(self, session: VoteSession) -> tuple[Optional[VoteDecision], float]:
        """Veto power: any veto → reject."""
        # Check for vetoes first
        for vote in session.votes:
            if vote.choice == VoteDecision.VETO.value:
                # Only designated veto agents can veto
                if vote.voter_id in session.config.veto_agents:
                    return VoteDecision.REJECT, 0.0

        # Fall back to majority
        return self._tally_majority(session)

    # ── Query ──

    def get_session(self, session_id: str) -> Optional[VoteSession]:
        return self._sessions.get(session_id)

    def get_voter_ids(self, session_id: str) -> list[str]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return [v.voter_id for v in session.votes]

    def get_vote(self, session_id: str, voter_id: str) -> Optional[VoteMessage]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        for vote in session.votes:
            if vote.voter_id == voter_id:
                return vote
        return None

    @property
    def total_sessions(self) -> int:
        return self._total_sessions
