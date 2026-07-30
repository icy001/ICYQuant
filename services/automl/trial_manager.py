"""Trial Manager.

Manages the lifecycle of AutoML trials: creation, execution,
result tracking, and parallel scheduling.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TrialStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrialTask:
    """A single trial to be executed."""

    trial_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: Dict[str, Any] = field(default_factory=dict)
    status: TrialStatus = TrialStatus.PENDING
    score: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrialResult:
    trial_id: str
    config: Dict[str, Any]
    score: float
    metrics: Dict[str, float] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


class TrialManager:
    """Manages the lifecycle of AutoML trials."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self.max_concurrent = max_concurrent
        self._trials: Dict[str, TrialTask] = {}
        self._completed: List[TrialResult] = []

    # ---- trial lifecycle ----

    def create_trial(self, config: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> TrialTask:
        task = TrialTask(config=config, metadata=metadata or {})
        self._trials[task.trial_id] = task
        return task

    def create_trials(self, configs: List[Dict[str, Any]]) -> List[TrialTask]:
        return [self.create_trial(c) for c in configs]

    def start_trial(self, trial_id: str) -> None:
        if trial_id not in self._trials:
            raise KeyError(f"Trial '{trial_id}' not found")
        task = self._trials[trial_id]
        if task.status != TrialStatus.PENDING:
            raise RuntimeError(f"Trial '{trial_id}' is {task.status.value}, cannot start")
        task.status = TrialStatus.RUNNING
        task.started_at = time.time()

    def complete_trial(self, trial_id: str, score: float, metrics: Optional[Dict[str, float]] = None) -> TrialResult:
        if trial_id not in self._trials:
            raise KeyError(f"Trial '{trial_id}' not found")
        task = self._trials[trial_id]
        task.status = TrialStatus.COMPLETED
        task.score = score
        task.metrics = metrics or {}
        task.completed_at = time.time()
        elapsed = (task.completed_at - task.started_at) if task.started_at else 0.0
        result = TrialResult(
            trial_id=task.trial_id,
            config=task.config,
            score=score,
            metrics=task.metrics,
            elapsed_seconds=elapsed,
        )
        self._completed.append(result)
        return result

    def fail_trial(self, trial_id: str, error: str) -> None:
        if trial_id not in self._trials:
            raise KeyError(f"Trial '{trial_id}' not found")
        task = self._trials[trial_id]
        task.status = TrialStatus.FAILED
        task.error = error
        task.completed_at = time.time()

    def cancel_trial(self, trial_id: str) -> None:
        if trial_id not in self._trials:
            raise KeyError(f"Trial '{trial_id}' not found")
        self._trials[trial_id].status = TrialStatus.CANCELLED

    def cancel_all(self) -> int:
        count = 0
        for task in self._trials.values():
            if task.status in (TrialStatus.PENDING, TrialStatus.RUNNING):
                task.status = TrialStatus.CANCELLED
                count += 1
        return count

    # ---- query ----

    def get_trial(self, trial_id: str) -> TrialTask:
        if trial_id not in self._trials:
            raise KeyError(f"Trial '{trial_id}' not found")
        return self._trials[trial_id]

    def get_pending(self) -> List[TrialTask]:
        return [t for t in self._trials.values() if t.status == TrialStatus.PENDING]

    def get_running(self) -> List[TrialTask]:
        return [t for t in self._trials.values() if t.status == TrialStatus.RUNNING]

    def get_completed(self) -> List[TrialTask]:
        return [t for t in self._trials.values() if t.status == TrialStatus.COMPLETED]

    def get_failed(self) -> List[TrialTask]:
        return [t for t in self._trials.values() if t.status == TrialStatus.FAILED]

    def best_result(self) -> Optional[TrialResult]:
        if not self._completed:
            return None
        return max(self._completed, key=lambda r: r.score)

    def best_config(self) -> Optional[Dict[str, Any]]:
        best = self.best_result()
        return best.config if best else None

    def results(self) -> List[TrialResult]:
        return list(self._completed)

    # ---- run ----

    def run_sequential(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        configs: List[Dict[str, Any]],
    ) -> List[TrialResult]:
        """Run trials sequentially and return results."""
        tasks = self.create_trials(configs)
        for task in tasks:
            self.start_trial(task.trial_id)
            try:
                score = objective_fn(task.config)
                self.complete_trial(task.trial_id, score)
            except Exception as e:
                self.fail_trial(task.trial_id, str(e))
        return self.results()

    # ---- stats ----

    def stats(self) -> Dict[str, Any]:
        best = self.best_result()
        running = self.get_running()
        return {
            "total": len(self._trials),
            "pending": len(self.get_pending()),
            "running": len(running),
            "completed": len(self.get_completed()),
            "failed": len(self.get_failed()),
            "best_score": best.score if best else None,
            "total_results": len(self._completed),
        }
