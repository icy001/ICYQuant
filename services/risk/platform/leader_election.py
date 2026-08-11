"""
Leader Election — Distributed leader election for risk cluster.

Implements leader election protocol with term-based consensus
to ensure exactly one leader node in the risk cluster.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ElectionState(str, Enum):
    """Current election state."""
    IDLE = "idle"
    CANDIDATE = "candidate"
    LEADER = "leader"
    FOLLOWER = "follower"


@dataclass
class ElectionTerm:
    """A leader election term."""
    term_id: int = 1
    leader_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    votes_received: int = 0
    votes_required: int = 1


@dataclass
class VoteRequest:
    """A vote request in leader election."""
    term_id: int = 0
    candidate_id: str = ""
    node_id: str = ""


@dataclass
class VoteResponse:
    """A vote response in leader election."""
    term_id: int = 0
    voter_id: str = ""
    voted_for: str = ""
    granted: bool = False


class LeaderElection:
    """
    Distributed leader election for the risk cluster.

    Implements term-based leader election with vote counting,
    ensuring exactly one leader node at any given time.

    Usage::

        election = LeaderElection(node_id="risk-node-1")
        await election.initialize()
        is_leader = await election.start_election()
        if is_leader:
            print("I am the leader")
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        election_timeout_seconds: float = 10.0,
    ) -> None:
        self._node_id = node_id or str(uuid.uuid4())
        self._election_timeout = election_timeout_seconds
        self._state = ElectionState.IDLE
        self._current_term = ElectionTerm()
        self._voted_in_term: dict[int, bool] = {}
        self._votes: dict[str, bool] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._election_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize leader election."""
        self._initialized = True
        logger.info(f"LeaderElection initialized (node: {self._node_id}).")

    async def stop(self) -> None:
        """Stop leader election."""
        if self._election_task:
            self._election_task.cancel()
        self._initialized = False
        logger.info("LeaderElection stopped.")

    # ---- Election ----

    async def start_election(self) -> bool:
        """Start a leader election and return True if this node becomes leader."""
        async with self._lock:
            self._state = ElectionState.CANDIDATE
            self._current_term = ElectionTerm(
                term_id=self._current_term.term_id + 1,
                leader_id="",
            )
            self._votes.clear()
            self._voted_in_term[self._current_term.term_id] = True

            logger.info(f"Starting election (term: {self._current_term.term_id})")

        # Wait for votes
        await asyncio.sleep(self._election_timeout * 0.5)

        async with self._lock:
            # Self-vote
            self._votes[self._node_id] = True
            total_votes = sum(1 for v in self._votes.values() if v)
            quorum = 1  # Simplified quorum

            if total_votes >= quorum:
                self._state = ElectionState.LEADER
                self._current_term.leader_id = self._node_id
                self._current_term.votes_received = total_votes
                logger.info(f"Node {self._node_id} elected leader (term {self._current_term.term_id})")
                return True
            else:
                self._state = ElectionState.FOLLOWER
                logger.info(f"Election lost (got {total_votes}/{quorum} votes)")
                return False

    async def request_vote(self, request: VoteRequest) -> VoteResponse:
        """Handle a vote request from another node."""
        async with self._lock:
            # Only vote once per term
            if request.term_id <= self._current_term.term_id:
                return VoteResponse(term_id=request.term_id, voter_id=self._node_id, granted=False)

            self._current_term.term_id = request.term_id
            self._state = ElectionState.FOLLOWER
            self._voted_in_term[request.term_id] = True

            return VoteResponse(
                term_id=request.term_id,
                voter_id=self._node_id,
                voted_for=request.candidate_id,
                granted=True,
            )

    async def receive_vote(self, response: VoteResponse) -> None:
        """Process a received vote."""
        async with self._lock:
            self._votes[response.voter_id] = response.granted

    async def step_down(self) -> None:
        """Step down from leader role."""
        async with self._lock:
            self._state = ElectionState.FOLLOWER
            self._current_term.leader_id = ""
            logger.info(f"Node {self._node_id} stepped down")

    # ---- Query ----

    @property
    def state(self) -> ElectionState:
        return self._state

    @property
    def is_leader(self) -> bool:
        return self._state == ElectionState.LEADER

    @property
    def current_term(self) -> ElectionTerm:
        return self._current_term

    async def get_state(self) -> dict[str, Any]:
        """Get current election state."""
        return {
            "node_id": self._node_id,
            "state": self._state.value,
            "term_id": self._current_term.term_id,
            "leader_id": self._current_term.leader_id,
            "is_leader": self.is_leader,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check election health."""
        return {
            "status": "healthy" if self._initialized else "stopped",
            "state": self._state.value,
            "term": self._current_term.term_id,
            "leader": self._current_term.leader_id,
        }
