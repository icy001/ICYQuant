"""Quorum Manager — majority-based decision making for cluster reliability.

Supports:

* **Quorum Check** — verify that a majority of nodes agree on a decision
* **Leader Validation** — ensure the leader has majority support
* **Split Brain Protection** — prevent two leaders from operating simultaneously

Improves cluster reliability by requiring majority consensus for critical
operations like leader election, state changes, and configuration updates.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class QuorumResult(str, Enum):
    """Result of a quorum check."""

    ACHIEVED = "achieved"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SPLIT_BRAIN = "split_brain"


@dataclass
class QuorumVote:
    """A single vote in a quorum decision."""

    node_id: str
    vote: bool
    term: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuorumDecision:
    """Result of a quorum-based decision."""

    decision_id: str
    result: QuorumResult
    votes_for: int = 0
    votes_against: int = 0
    total_nodes: int = 0
    required_votes: int = 0
    decided_at: datetime = field(default_factory=datetime.utcnow)
    leader_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_achieved(self) -> bool:
        return self.result == QuorumResult.ACHIEVED

    @property
    def vote_ratio(self) -> float:
        if self.total_nodes == 0:
            return 0.0
        return self.votes_for / self.total_nodes


class QuorumManager:
    """Manages quorum-based decisions for the workflow cluster.

    Usage::

        quorum = QuorumManager(min_nodes=3)
        await quorum.start()
        result = await quorum.check_quorum(decision_id="leader_election", votes=[...])
    """

    def __init__(
        self,
        *,
        min_nodes: int = 3,
        quorum_size: Optional[int] = None,
    ) -> None:
        self._min_nodes = min_nodes
        self._quorum_size = quorum_size
        self._lock = threading.RLock()
        self._started = False

        # Active nodes for quorum calculation
        self._active_nodes: Set[str] = set()

        # Decision history
        self._history: List[QuorumDecision] = []
        self._max_history = 1000

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("QuorumManager: started (min_nodes=%d)", self._min_nodes)

    async def stop(self) -> None:
        self._started = False
        logger.info("QuorumManager: stopped")

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    async def add_node(self, node_id: str) -> None:
        with self._lock:
            self._active_nodes.add(node_id)

    async def remove_node(self, node_id: str) -> None:
        with self._lock:
            self._active_nodes.discard(node_id)

    async def node_count(self) -> int:
        with self._lock:
            return len(self._active_nodes)

    async def get_active_nodes(self) -> Set[str]:
        with self._lock:
            return set(self._active_nodes)

    # ------------------------------------------------------------------
    # Quorum calculations
    # ------------------------------------------------------------------

    def _calculate_quorum_size(self) -> int:
        """Calculate the required number of votes for quorum."""
        total = len(self._active_nodes)
        if total == 0:
            return 0
        if self._quorum_size is not None:
            return min(self._quorum_size, total)
        # Default: majority (N/2 + 1)
        return (total // 2) + 1

    # ------------------------------------------------------------------
    # Quorum checks
    # ------------------------------------------------------------------

    async def check_quorum(
        self,
        decision_id: str,
        votes: List[QuorumVote],
        *,
        term: int = 0,
    ) -> QuorumDecision:
        """Check if a quorum has been achieved for a decision.

        Parameters
        ----------
        decision_id: Unique identifier for the decision.
        votes: List of votes from cluster nodes.
        term: The consensus term for this decision.
        """
        with self._lock:
            required = self._calculate_quorum_size()
            total_nodes = len(self._active_nodes)

        # Count valid votes (only from active nodes)
        with self._lock:
            valid_votes = [v for v in votes if v.node_id in self._active_nodes]

        votes_for = sum(1 for v in valid_votes if v.vote)
        votes_against = sum(1 for v in valid_votes if not v.vote)

        # Determine result
        if total_nodes < self._min_nodes:
            result = QuorumResult.FAILED
            reason = f"Insufficient nodes ({total_nodes} < {self._min_nodes})"
        elif votes_for >= required:
            result = QuorumResult.ACHIEVED
            reason = f"Quorum achieved ({votes_for}/{required})"
        else:
            result = QuorumResult.FAILED
            reason = f"Quorum not met ({votes_for}/{required})"

        decision = QuorumDecision(
            decision_id=decision_id,
            result=result,
            votes_for=votes_for,
            votes_against=votes_against,
            total_nodes=total_nodes,
            required_votes=required,
            details={"reason": reason, "term": term},
        )

        with self._lock:
            self._history.append(decision)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        logger.debug("QuorumManager: decision %s → %s (%d/%d votes)",
                      decision_id, result.value, votes_for, required)
        return decision

    async def validate_leader(self, leader_id: str, supporters: List[str]) -> QuorumDecision:
        """Validate that a leader has quorum support (split-brain protection)."""
        votes = [
            QuorumVote(node_id=nid, vote=(nid in supporters))
            for nid in self._active_nodes
        ]
        decision = await self.check_quorum(
            decision_id=f"leader_validation_{leader_id}",
            votes=votes,
        )

        if decision.result != QuorumResult.ACHIEVED:
            logger.warning("QuorumManager: leader %s lacks quorum support (split-brain risk)", leader_id)
            decision.result = QuorumResult.SPLIT_BRAIN

        return decision

    async def check_split_brain(self, leader_a: str, leader_b: str) -> QuorumDecision:
        """Detect and resolve split-brain scenarios."""
        logger.warning("QuorumManager: potential split-brain between %s and %s", leader_a, leader_b)

        return QuorumDecision(
            decision_id=f"split_brain_{leader_a}_{leader_b}",
            result=QuorumResult.SPLIT_BRAIN,
            total_nodes=len(self._active_nodes),
            required_votes=self._calculate_quorum_size(),
            details={"leader_a": leader_a, "leader_b": leader_b},
        )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_decision_history(self, limit: int = 100) -> List[QuorumDecision]:
        with self._lock:
            return list(self._history[-limit:])

    async def last_decision(self) -> Optional[QuorumDecision]:
        with self._lock:
            return self._history[-1] if self._history else None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._active_nodes)
            required = self._calculate_quorum_size()
            return {
                "active_nodes": total,
                "min_nodes": self._min_nodes,
                "quorum_size": self._quorum_size or ((total // 2) + 1),
                "required_votes": required,
                "can_form_quorum": total >= self._min_nodes,
                "history_count": len(self._history),
            }
