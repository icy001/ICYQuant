"""Goal Manager — defines, tracks, and decomposes high-level user goals for autonomous execution.

Pipeline:
    User Goal -> GoalManager.create_goal()
        -> Decompose into sub-goals
        -> Track progress per sub-goal
        -> Mark completed / failed
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    """A high-level goal with optional sub-goals.

    Attributes:
        goal_id: Unique goal identifier.
        title: Short description of the goal.
        description: Detailed description.
        status: Current status.
        parent_id: Optional parent goal for hierarchical decomposition.
        sub_goals: Child goals.
        metadata: Additional context.
        created_at: Creation timestamp.
        completed_at: Completion timestamp.
    """

    goal_id: str = ""
    title: str = ""
    description: str = ""
    status: GoalStatus = GoalStatus.PENDING
    parent_id: Optional[str] = None
    sub_goals: List[Goal] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED)

    @property
    def progress(self) -> float:
        if not self.sub_goals:
            return 1.0 if self.status == GoalStatus.COMPLETED else 0.0
        completed = sum(1 for g in self.sub_goals if g.status == GoalStatus.COMPLETED)
        return completed / len(self.sub_goals)


class GoalManager:
    """Manages goal lifecycle, decomposition, and progress tracking.

    Supports:
        - Goal creation and hierarchical decomposition
        - Progress tracking across sub-goals
        - Goal cancellation and status transitions
        - Metadata enrichment

    Usage:
        gm = GoalManager()
        goal = await gm.create_goal("Analyze AAPL", "Conduct full analysis of AAPL")
        await gm.decompose(goal, ["Gather market data", "Run backtest", "Generate report"])
        await gm.mark_completed(sub_goal)
    """

    def __init__(self, max_goals: int = 1000) -> None:
        self._goals: Dict[str, Goal] = {}
        self._max_goals = max_goals
        self._initialized: bool = False
        logger.info("GoalManager created (max_goals=%d)", max_goals)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("GoalManager initialized")

    async def shutdown(self) -> None:
        self._goals.clear()
        self._initialized = False
        logger.info("GoalManager shutdown complete")

    async def create_goal(
        self,
        title: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        goal_id = f"goal_{int(time.time() * 1000)}_{len(self._goals)}"
        goal = Goal(
            goal_id=goal_id,
            title=title,
            description=description,
            metadata=metadata or {},
        )
        self._goals[goal_id] = goal
        self._evict_oldest_if_needed()
        logger.info("Goal created: %s (%s)", goal_id, title)
        return goal

    async def decompose(self, goal: Goal, sub_titles: List[str]) -> List[Goal]:
        sub_goals = []
        for title in sub_titles:
            sub = await self.create_goal(title, parent_id=goal.goal_id)
            sub.parent_id = goal.goal_id
            sub_goals.append(sub)
        goal.sub_goals.extend(sub_goals)
        logger.info("Goal %s decomposed into %d sub-goals", goal.goal_id, len(sub_goals))
        return sub_goals

    async def start_goal(self, goal: Goal) -> None:
        goal.status = GoalStatus.IN_PROGRESS
        logger.debug("Goal started: %s", goal.goal_id)

    async def mark_completed(self, goal: Goal) -> None:
        goal.status = GoalStatus.COMPLETED
        goal.completed_at = datetime.now(timezone.utc)
        logger.info("Goal completed: %s", goal.goal_id)

    async def mark_failed(self, goal: Goal, reason: str = "") -> None:
        goal.status = GoalStatus.FAILED
        goal.completed_at = datetime.now(timezone.utc)
        goal.metadata["failure_reason"] = reason
        logger.warning("Goal failed: %s (reason=%s)", goal.goal_id, reason)

    async def cancel_goal(self, goal: Goal) -> None:
        goal.status = GoalStatus.CANCELLED
        goal.completed_at = datetime.now(timezone.utc)
        for sub in goal.sub_goals:
            if not sub.is_terminal:
                await self.cancel_goal(sub)
        logger.info("Goal cancelled: %s", goal.goal_id)

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def get_active_goals(self) -> List[Goal]:
        return [g for g in self._goals.values() if g.status == GoalStatus.IN_PROGRESS]

    def get_summary(self) -> Dict[str, Any]:
        total = len(self._goals)
        completed = sum(1 for g in self._goals.values() if g.status == GoalStatus.COMPLETED)
        failed = sum(1 for g in self._goals.values() if g.status == GoalStatus.FAILED)
        in_progress = sum(1 for g in self._goals.values() if g.status == GoalStatus.IN_PROGRESS)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "initialized": self._initialized,
        }

    def _evict_oldest_if_needed(self) -> None:
        if len(self._goals) <= self._max_goals:
            return
        completed = sorted(
            [g for g in self._goals.values() if g.is_terminal],
            key=lambda g: g.created_at,
        )
        to_remove = completed[: len(self._goals) - self._max_goals + 10]
        for g in to_remove:
            self._goals.pop(g.goal_id, None)
