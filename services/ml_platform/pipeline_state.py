"""
ICYQuant Pipeline State - ML pipeline state management.

Tracks the state of every pipeline run for observability,
recovery, and debugging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PipelineRunStatus(Enum):
    """Pipeline run lifecycle states."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class StepStatus(Enum):
    """Individual pipeline step status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepState:
    """State of a single pipeline step."""

    step_name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    input_artifacts: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class PipelineState:
    """Complete state of a pipeline run."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    pipeline_name: str = ""
    status: PipelineRunStatus = PipelineRunStatus.PENDING

    # Steps
    steps: Dict[str, StepState] = field(default_factory=dict)
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_step: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0

    # Context
    input_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Resources
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    # Error
    error: Optional[str] = None
    error_step: Optional[str] = None

    @property
    def progress(self) -> float:
        """Pipeline progress as 0.0 - 1.0."""
        total = len(self.steps)
        if total == 0:
            return 1.0 if self.status == PipelineRunStatus.COMPLETED else 0.0
        completed = len([s for s in self.steps.values() if s.status == StepStatus.COMPLETED])
        return completed / total


class PipelineStateManager:
    """Manages pipeline run state tracking.

    Provides:
    - Real-time pipeline state observation
    - Step-level progress tracking
    - State persistence for recovery
    - Pipeline run history
    """

    def __init__(self) -> None:
        self._active_runs: Dict[str, PipelineState] = {}
        self._run_history: List[PipelineState] = []

    # -- State Management --

    def create_run(self, pipeline_name: str, steps: List[str], params: Optional[Dict[str, Any]] = None) -> PipelineState:
        """Create a new pipeline run state."""
        state = PipelineState(
            pipeline_name=pipeline_name,
            input_params=params or {},
        )

        for step_name in steps:
            state.steps[step_name] = StepState(step_name=step_name)

        self._active_runs[state.run_id] = state
        logger.info("Pipeline run created: %s (%s, %d steps)", state.run_id, pipeline_name, len(steps))
        return state

    def start_run(self, run_id: str) -> None:
        """Mark a pipeline run as started."""
        state = self._active_runs.get(run_id)
        if state:
            state.status = PipelineRunStatus.RUNNING
            state.started_at = datetime.utcnow()

    def start_step(self, run_id: str, step_name: str) -> None:
        """Mark a step as started."""
        state = self._active_runs.get(run_id)
        if state and step_name in state.steps:
            state.steps[step_name].status = StepStatus.RUNNING
            state.steps[step_name].started_at = datetime.utcnow()
            state.current_step = step_name

    def complete_step(self, run_id: str, step_name: str, output_artifacts: Optional[List[str]] = None) -> None:
        """Mark a step as completed."""
        state = self._active_runs.get(run_id)
        if state and step_name in state.steps:
            step = state.steps[step_name]
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            if step.started_at:
                step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
            if output_artifacts:
                step.output_artifacts = output_artifacts
            state.completed_steps.append(step_name)

    def fail_step(self, run_id: str, step_name: str, error: str) -> None:
        """Mark a step as failed."""
        state = self._active_runs.get(run_id)
        if state and step_name in state.steps:
            step = state.steps[step_name]
            step.status = StepStatus.FAILED
            step.error = error
            step.completed_at = datetime.utcnow()
            state.failed_step = step_name
            state.error = error
            state.error_step = step_name

    def complete_run(self, run_id: str) -> None:
        """Mark a pipeline run as completed."""
        state = self._active_runs.get(run_id)
        if state:
            state.status = PipelineRunStatus.COMPLETED
            state.completed_at = datetime.utcnow()
            if state.started_at:
                state.total_duration_seconds = (state.completed_at - state.started_at).total_seconds()
            self._archive_run(state)

    def fail_run(self, run_id: str, error: str) -> None:
        """Mark a pipeline run as failed."""
        state = self._active_runs.get(run_id)
        if state:
            state.status = PipelineRunStatus.FAILED
            state.error = error
            state.completed_at = datetime.utcnow()
            self._archive_run(state)

    def _archive_run(self, state: PipelineState) -> None:
        """Move a run from active to history."""
        self._active_runs.pop(state.run_id, None)
        self._run_history.append(state)

    # -- Query --

    def get_run(self, run_id: str) -> Optional[PipelineState]:
        """Get a pipeline run state (active or historical)."""
        state = self._active_runs.get(run_id)
        if state:
            return state
        for s in self._run_history:
            if s.run_id == run_id:
                return s
        return None

    def get_active_runs(self) -> List[PipelineState]:
        """Get all currently active runs."""
        return list(self._active_runs.values())

    def get_recent_runs(self, limit: int = 20) -> List[PipelineState]:
        """Get recent pipeline runs from history."""
        return sorted(self._run_history, key=lambda s: s.created_at, reverse=True)[:limit]
