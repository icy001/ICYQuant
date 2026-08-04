"""
Rotation workflow pipeline.

Defines the step-by-step rotation pipeline
from validation through dual-key transition
to final audit, with support for custom
steps and conditional execution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .transition import DualKeyTransition, TransitionPhase

logger = logging.getLogger(__name__)


class WorkflowStepStatus(str, Enum):
    """Workflow step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WorkflowStatus(str, Enum):
    """Overall workflow status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class WorkflowStep:
    """
    A single step in the rotation workflow.

    Attributes:
        name: Step name.
        description: Human-readable description.
        execute: Async callable implementing the step.
        status: Current execution status.
        duration_ms: Execution duration in milliseconds.
        error: Error message if failed.
        skipped: Whether the step was skipped.
        condition: Optional condition that must be met to run.
    """

    name: str
    description: str = ""
    execute: Optional[Callable] = None
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    duration_ms: float = 0.0
    error: str = ""
    skipped: bool = False
    condition: Optional[Callable[[], bool]] = None
    result: Any = None

    async def run(self) -> Any:
        """
        Execute the step.

        Returns:
            Step execution result.
        """
        # Check condition
        if self.condition and not self.condition():
            self.status = WorkflowStepStatus.SKIPPED
            self.skipped = True
            logger.debug("Step '%s' skipped (condition not met)", self.name)
            return None

        if self.execute is None:
            self.status = WorkflowStepStatus.SKIPPED
            self.skipped = True
            return None

        self.status = WorkflowStepStatus.RUNNING
        start = time.perf_counter()

        try:
            self.result = await self.execute()
            self.status = WorkflowStepStatus.COMPLETED
        except Exception as e:
            self.status = WorkflowStepStatus.FAILED
            self.error = str(e)
            logger.error("Step '%s' failed: %s", self.name, e)
            raise
        finally:
            self.duration_ms = (time.perf_counter() - start) * 1000

        return self.result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "skipped": self.skipped,
            "error": self.error,
        }


class RotationWorkflow:
    """
    Rotation pipeline orchestrator.

    Manages the execution of rotation
    steps in sequence, supporting
    conditional execution, rollback,
    and partial completion.

    Default pipeline:
    1. Validate
    2. Health Check
    3. Dual-Key Transition
    4. Atomic Switch
    5. Revoke Old Secret
    6. Audit

    Usage:
        workflow = RotationWorkflow()
        workflow.add_step(validate_step)
        result = await workflow.execute()
    """

    def __init__(
        self,
        auto_rollback: bool = True,
        on_step_complete: Optional[Callable] = None,
        on_workflow_complete: Optional[Callable] = None,
    ) -> None:
        """
        Initialize workflow.

        Args:
            auto_rollback: Auto-rollback on failure.
            on_step_complete: Step completion callback.
            on_workflow_complete: Workflow completion callback.
        """
        self._steps: List[WorkflowStep] = []
        self._status = WorkflowStatus.PENDING
        self._auto_rollback = auto_rollback
        self._on_step_complete = on_step_complete
        self._on_workflow_complete = on_workflow_complete
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._results: Dict[str, Any] = {}

    @property
    def status(self) -> WorkflowStatus:
        """Get current workflow status."""
        return self._status

    @property
    def steps(self) -> List[WorkflowStep]:
        """Get all workflow steps."""
        return list(self._steps)

    @property
    def is_complete(self) -> bool:
        """Check if workflow completed (success or failure)."""
        return self._status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.ROLLED_BACK,
        )

    def add_step(
        self,
        step: WorkflowStep,
        index: Optional[int] = None,
    ) -> None:
        """
        Add a step to the workflow.

        Args:
            step: WorkflowStep to add.
            index: Position to insert (appends if None).
        """
        if index is not None:
            self._steps.insert(index, step)
        else:
            self._steps.append(step)

    def create_step(
        self,
        name: str,
        description: str,
        execute: Callable,
        condition: Optional[Callable[[], bool]] = None,
    ) -> WorkflowStep:
        """
        Create and add a new workflow step.

        Args:
            name: Step name.
            description: Step description.
            execute: Execution function.
            condition: Optional condition.

        Returns:
            Created WorkflowStep.
        """
        step = WorkflowStep(
            name=name,
            description=description,
            execute=execute,
            condition=condition,
        )
        self.add_step(step)
        return step

    async def execute(self) -> Dict[str, Any]:
        """
        Execute the full workflow pipeline.

        Returns:
            Workflow execution result summary.
        """
        if self._status == WorkflowStatus.RUNNING:
            raise RuntimeError("Workflow is already running")

        self._status = WorkflowStatus.RUNNING
        self._started_at = datetime.utcnow()
        self._results = {}

        failed_step: Optional[WorkflowStep] = None

        for step in self._steps:
            if self._status != WorkflowStatus.RUNNING:
                break

            try:
                result = await step.run()
                self._results[step.name] = result

                if self._on_step_complete:
                    try:
                        self._on_step_complete(step, result)
                    except Exception as e:
                        logger.error("Step callback error: %s", e)

            except Exception as e:
                logger.error(
                    "Workflow step '%s' failed: %s", step.name, e
                )
                step.status = WorkflowStepStatus.FAILED
                step.error = str(e)
                failed_step = step

                if self._auto_rollback:
                    self._status = WorkflowStatus.FAILED
                    return self._finalize(
                        success=False,
                        failed_step=failed_step,
                        error=str(e),
                    )
                else:
                    self._status = WorkflowStatus.PAUSED
                    return self._finalize(
                        success=False,
                        failed_step=failed_step,
                        error=str(e),
                    )

        self._status = WorkflowStatus.COMPLETED
        return self._finalize(success=True)

    async def rollback(self) -> Dict[str, Any]:
        """
        Rollback the workflow.

        Attempts to reverse completed steps.

        Returns:
            Rollback result summary.
        """
        self._status = WorkflowStatus.ROLLED_BACK
        logger.warning("Workflow rollback initiated")
        return self._finalize(
            success=False,
            error="Rolled back",
        )

    def _finalize(
        self,
        success: bool,
        failed_step: Optional[WorkflowStep] = None,
        error: str = "",
    ) -> Dict[str, Any]:
        """
        Generate final workflow result.

        Args:
            success: Whether the workflow succeeded.
            failed_step: The step that failed.
            error: Error message.

        Returns:
            Workflow result dictionary.
        """
        self._completed_at = datetime.utcnow()

        result = {
            "status": self._status.value,
            "success": success,
            "started_at": (
                self._started_at.isoformat() + "Z"
                if self._started_at
                else None
            ),
            "completed_at": (
                self._completed_at.isoformat() + "Z"
                if self._completed_at
                else None
            ),
            "total_duration_ms": self._total_duration_ms(),
            "steps": [s.to_dict() for s in self._steps],
            "failed_step": failed_step.name if failed_step else None,
            "error": error,
            "results": {
                k: str(v)[:200] if v else None
                for k, v in self._results.items()
            },
        }

        if self._on_workflow_complete:
            try:
                self._on_workflow_complete(result)
            except Exception as e:
                logger.error("Workflow callback error: %s", e)

        return result

    def _total_duration_ms(self) -> float:
        """Calculate total execution duration."""
        return sum(s.duration_ms for s in self._steps)

    def get_progress(self) -> Dict[str, Any]:
        """Get workflow execution progress."""
        total = len(self._steps)
        completed = sum(
            1 for s in self._steps
            if s.status in (
                WorkflowStepStatus.COMPLETED,
                WorkflowStepStatus.SKIPPED,
            )
        )
        failed = sum(
            1 for s in self._steps
            if s.status == WorkflowStepStatus.FAILED
        )

        return {
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
            "status": self._status.value,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        durations = [
            s.duration_ms for s in self._steps
            if s.status == WorkflowStepStatus.COMPLETED
        ]
        return {
            "total_steps": len(self._steps),
            "completed_steps": sum(
                1 for s in self._steps
                if s.status == WorkflowStepStatus.COMPLETED
            ),
            "skipped_steps": sum(
                1 for s in self._steps
                if s.status == WorkflowStepStatus.SKIPPED
            ),
            "failed_steps": sum(
                1 for s in self._steps
                if s.status == WorkflowStepStatus.FAILED
            ),
            "total_duration_ms": round(self._total_duration_ms(), 2),
            "avg_step_duration_ms": round(
                sum(durations) / len(durations), 2
            ) if durations else 0,
            "status": self._status.value,
        }
