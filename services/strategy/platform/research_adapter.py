"""
Research Adapter — Connects Strategy Platform to the Research Platform.

Provides interface for submitting research tasks, retrieving results,
and bridging research outputs to production strategies.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResearchTaskStatus(str, Enum):
    """Research task status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ResearchTask:
    """Research task definition."""
    task_id: str
    strategy_id: str
    task_type: str  # backtest, optimization, analysis, etc.
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    status: ResearchTaskStatus = ResearchTaskStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """Research task result."""
    task_id: str
    strategy_id: str
    status: ResearchTaskStatus
    output: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)  # Paths to result files
    started_at: Optional[datetime] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


class ResearchAdapter:
    """
    Adapter for the Research Platform.

    Bridges research outputs (backtests, optimizations, analyses)
    to production strategy deployment through a standardized interface.

    Usage::

        adapter = ResearchAdapter()
        await adapter.initialize()
        task = await adapter.submit_task(ResearchTask(
            task_id="backtest_001",
            strategy_id="strat_001",
            task_type="backtest",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        ))
        result = await adapter.get_result(task.task_id)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ResearchTask] = {}
        self._results: dict[str, ResearchResult] = {}
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the research adapter."""
        self._initialized = True
        logger.info("ResearchAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("ResearchAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def submit_task(self, task: ResearchTask) -> ResearchTask:
        """Submit a research task."""
        if task.task_id in self._tasks:
            raise ValueError(f"Task already exists: {task.task_id}")

        self._tasks[task.task_id] = task
        task.status = ResearchTaskStatus.RUNNING

        # Simulate research completion
        task.status = ResearchTaskStatus.COMPLETED
        self._results[task.task_id] = ResearchResult(
            task_id=task.task_id,
            strategy_id=task.strategy_id,
            status=ResearchTaskStatus.COMPLETED,
            started_at=task.created_at,
        )

        logger.info(f"Research task submitted: {task.task_id} ({task.task_type})")
        return task

    async def get_task(self, task_id: str) -> Optional[ResearchTask]:
        """Get a research task by ID."""
        return self._tasks.get(task_id)

    async def get_result(self, task_id: str) -> Optional[ResearchResult]:
        """Get the result of a research task."""
        return self._results.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running research task."""
        task = self._tasks.get(task_id)
        if not task or task.status not in (ResearchTaskStatus.QUEUED, ResearchTaskStatus.RUNNING):
            return False
        task.status = ResearchTaskStatus.CANCELLED
        logger.info(f"Research task cancelled: {task_id}")
        return True

    async def list_tasks(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[ResearchTaskStatus] = None,
        limit: int = 100,
    ) -> list[ResearchTask]:
        """List research tasks with filters."""
        results = list(self._tasks.values())
        if strategy_id:
            results = [t for t in results if t.strategy_id == strategy_id]
        if status:
            results = [t for t in results if t.status == status]
        return sorted(results, key=lambda t: t.created_at, reverse=True)[:limit]

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tasks_tracked": len(self._tasks),
            "results_available": len(self._results),
        }
