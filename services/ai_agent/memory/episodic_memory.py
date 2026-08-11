"""
Episodic memory for historical task trajectories.

Records complete agent execution episodes with all context,
decisions, and outcomes for future reference and learning.

Responsibility: Historical task trajectories and experience replay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Episode Types ──


class EpisodeStatus(str, Enum):
    """Episode completion status."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class EpisodeStep:
    """A single step within an episode."""

    step_index: int = 0
    action: str = ""
    input_summary: str = ""
    output_summary: str = ""
    success: bool = True
    duration_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Episode:
    """A complete agent execution episode.

    Captures the full trajectory: goal → plan → reasoning → execution → outcome.
    """

    episode_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    goal: str = ""
    plan_id: str = ""
    status: EpisodeStatus = EpisodeStatus.SUCCESS
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    steps: List[EpisodeStep] = field(default_factory=list)
    plan_summary: Dict[str, Any] = field(default_factory=dict)
    reasoning_summary: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    agent_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: EpisodeStep) -> None:
        """Add a step to the episode."""
        self.steps.append(step)

    def complete(self, status: EpisodeStatus) -> None:
        """Mark episode as complete."""
        self.status = status
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert episode to dictionary."""
        return {
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "goal": self.goal[:100],
            "status": self.status.value,
            "step_count": len(self.steps),
            "duration_seconds": self.total_duration_seconds,
            "agent_type": self.agent_type,
            "tags": self.tags,
        }


# ── Episodic Memory ──


class EpisodicMemory:
    """Storage for agent execution episodes.

    Records full execution trajectories for:
        - Historical reference and pattern recognition
        - Experience replay and learning
        - Performance analysis and optimization
        - Audit and compliance tracking

    Usage:
        em = EpisodicMemory()
        ep = em.record_episode(Episode(session_id="s1", goal="Analyze market"))
        similar = em.find_similar_episodes("market analysis")
    """

    def __init__(self, max_episodes: int = 10000) -> None:
        self.max_episodes = max_episodes
        self._episodes: Dict[str, Episode] = {}
        self._index_by_session: Dict[str, List[str]] = {}
        self._index_by_tag: Dict[str, List[str]] = {}
        logger.info("EpisodicMemory created")

    # ── CRUD ──

    def record_episode(self, episode: Episode) -> Episode:
        """Store a completed episode.

        Args:
            episode: The episode to store.

        Returns:
            The stored episode.
        """
        # Enforce max capacity
        if len(self._episodes) >= self.max_episodes:
            oldest = min(
                self._episodes.values(),
                key=lambda e: e.created_at,
            )
            del self._episodes[oldest.episode_id]

        self._episodes[episode.episode_id] = episode

        # Update session index
        if episode.session_id:
            self._index_by_session.setdefault(episode.session_id, [])
            self._index_by_session[episode.session_id].append(episode.episode_id)

        # Update tag index
        for tag in episode.tags:
            self._index_by_tag.setdefault(tag, [])
            self._index_by_tag[tag].append(episode.episode_id)

        logger.debug(f"Episode recorded: {episode.episode_id} [{episode.status.value}]")
        return episode

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        return self._episodes.get(episode_id)

    def get_by_session(self, session_id: str) -> List[Episode]:
        """Get all episodes for a session."""
        episode_ids = self._index_by_session.get(session_id, [])
        return [self._episodes[eid] for eid in episode_ids if eid in self._episodes]

    # ── Query ──

    def find_by_status(self, status: EpisodeStatus) -> List[Episode]:
        """Find episodes by status."""
        return [e for e in self._episodes.values() if e.status == status]

    def find_by_tag(self, tag: str) -> List[Episode]:
        """Find episodes by tag."""
        episode_ids = self._index_by_tag.get(tag, [])
        return [self._episodes[eid] for eid in episode_ids if eid in self._episodes]

    def find_by_agent_type(self, agent_type: str) -> List[Episode]:
        """Find episodes by agent type."""
        return [e for e in self._episodes.values() if e.agent_type == agent_type]

    def find_similar_episodes(self, query: str, limit: int = 10) -> List[Episode]:
        """Find episodes similar to a query (keyword-based).

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            Matching episodes.
        """
        query_lower = query.lower()
        scored: List[tuple] = []

        for episode in self._episodes.values():
            score = 0
            if query_lower in episode.goal.lower():
                score += 3
            if any(query_lower in s.action.lower() for s in episode.steps):
                score += 1
            if any(query_lower in t.lower() for t in episode.tags):
                score += 2
            if score > 0:
                scored.append((score, episode))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def get_recent(self, limit: int = 10) -> List[Episode]:
        """Get most recent episodes."""
        sorted_eps = sorted(
            self._episodes.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return sorted_eps[:limit]

    # ── Analysis ──

    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if not self._episodes:
            return 0.0
        successes = sum(
            1 for e in self._episodes.values()
            if e.status == EpisodeStatus.SUCCESS
        )
        return successes / len(self._episodes)

    def get_average_duration(self) -> float:
        """Average episode duration."""
        durations = [e.total_duration_seconds for e in self._episodes.values()]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    # ── Status ──

    @property
    def size(self) -> int:
        """Total stored episodes."""
        return len(self._episodes)

    def get_summary(self) -> Dict[str, Any]:
        """Get episodic memory summary."""
        status_counts: Dict[str, int] = {}
        for e in self._episodes.values():
            s = e.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total_episodes": self.size,
            "by_status": status_counts,
            "success_rate": self.get_success_rate(),
            "average_duration_seconds": self.get_average_duration(),
            "unique_sessions": len(self._index_by_session),
            "unique_tags": len(self._index_by_tag),
        }
