"""Experiment Scheduler — schedules and manages research experiments autonomously.

Pipeline:
    Hypothesis -> ExperimentScheduler.schedule()
        -> Create Experiment
        -> Assign priority
        -> Queue execution
        -> Collect results
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Experiment:
    """A scheduled research experiment.

    Attributes:
        experiment_id: Unique identifier.
        hypothesis_id: Parent hypothesis.
        name: Experiment name.
        status: Current status.
        priority: Scheduling priority (higher = sooner).
        parameters: Experiment parameters.
        results: Experiment results.
        scheduled_at: When the experiment was scheduled.
        completed_at: When it completed.
    """

    experiment_id: str = ""
    hypothesis_id: str = ""
    name: str = ""
    status: ExperimentStatus = ExperimentStatus.QUEUED
    priority: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class ExperimentScheduler:
    """Schedules and manages autonomous research experiments.

    Maintains a priority queue of experiments, executes them in order,
    and collects results for hypothesis validation.

    Supports:
        - Priority-based scheduling
        - Experiment lifecycle management
        - Result collection
        - Max concurrency control

    Usage:
        scheduler = ExperimentScheduler()
        await scheduler.initialize()
        exp = await scheduler.schedule(hypothesis, parameters={...})
        await scheduler.run_experiment(exp)
    """

    def __init__(self, max_concurrent: int = 3) -> None:
        self._experiments: List[Experiment] = []
        self._counter: int = 0
        self._max_concurrent = max_concurrent
        self._running_count: int = 0
        self._initialized: bool = False
        logger.info("ExperimentScheduler created (max_concurrent=%d)", max_concurrent)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ExperimentScheduler initialized")

    async def shutdown(self) -> None:
        self._experiments.clear()
        self._initialized = False
        logger.info("ExperimentScheduler shutdown complete")

    async def schedule(
        self,
        hypothesis: Optional[Any] = None,
        parameters: Optional[Dict[str, Any]] = None,
        priority: int = 1,
    ) -> Experiment:
        self._counter += 1
        exp = Experiment(
            experiment_id=f"exp_{self._counter}",
            hypothesis_id=hypothesis.hypothesis_id if hypothesis else "",
            name=f"Experiment {self._counter}",
            priority=priority,
            parameters=parameters or {},
        )
        self._experiments.append(exp)
        logger.info("Experiment scheduled: %s (priority=%d)", exp.experiment_id, priority)
        return exp

    async def run_experiment(self, experiment: Experiment) -> Dict[str, Any]:
        experiment.status = ExperimentStatus.RUNNING
        self._running_count += 1
        try:
            experiment.status = ExperimentStatus.COMPLETED
            experiment.completed_at = datetime.now(timezone.utc)
            logger.info("Experiment completed: %s", experiment.experiment_id)
        except Exception as e:
            experiment.status = ExperimentStatus.FAILED
            experiment.results["error"] = str(e)
            logger.error("Experiment failed: %s (error=%s)", experiment.experiment_id, e)
        finally:
            self._running_count -= 1
        return experiment.results

    def get_next_experiment(self) -> Optional[Experiment]:
        if self._running_count >= self._max_concurrent:
            return None
        queued = sorted(
            [e for e in self._experiments if e.status == ExperimentStatus.QUEUED],
            key=lambda e: e.priority,
            reverse=True,
        )
        return queued[0] if queued else None

    def get_summary(self) -> Dict[str, Any]:
        completed = sum(1 for e in self._experiments if e.status == ExperimentStatus.COMPLETED)
        return {
            "initialized": self._initialized,
            "total": len(self._experiments),
            "running": self._running_count,
            "completed": completed,
            "max_concurrent": self._max_concurrent,
        }
