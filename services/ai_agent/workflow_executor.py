"""
Workflow executor for translating plans into execution.

Converts execution plans into actionable workflows and manages
the step-by-step execution with result aggregation.

Pipeline:
    Plan → Workflow → Task → Result
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.planner import Plan, PlanStep
from services.ai_agent.reasoning_engine import ReasoningResult

logger = logging.getLogger(__name__)


# ── Workflow Types ──


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepResultStatus(str, Enum):
    """Individual step execution result."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    RETRYING = "retrying"


@dataclass
class StepResult:
    """Result of executing a single plan step."""

    step_id: str
    step_name: str
    status: StepResultStatus = StepResultStatus.SUCCESS
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_seconds: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Aggregated result of workflow execution."""

    workflow_id: str = field(default_factory=lambda: uuid4().hex)
    plan_id: str = ""
    session_id: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    step_results: List[StepResult] = field(default_factory=list)
    final_output: Any = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_summary(self) -> Dict[str, Any]:
        """Generate workflow result summary."""
        success_count = sum(1 for r in self.step_results if r.status == StepResultStatus.SUCCESS)
        failed_count = sum(1 for r in self.step_results if r.status == StepResultStatus.FAILED)
        return {
            "workflow_id": self.workflow_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "step_results": f"{success_count} success, {failed_count} failed",
            "total_steps": len(self.step_results),
            "duration_seconds": self.total_duration_seconds,
        }


# ── Workflow Executor ──


class WorkflowExecutor:
    """Executes plans as workflows with step-by-step execution.

    Translates Plan objects into executable workflows, manages
    dependency resolution, and aggregates step results.

    Usage:
        executor = WorkflowExecutor()
        result = await executor.execute(plan=plan, reasoning=reasoning)
    """

    def __init__(self) -> None:
        self._active_workflows: Dict[str, WorkflowResult] = {}
        self._execution_count: int = 0
        logger.info("WorkflowExecutor initialized")

    # ── Execution ──

    async def execute(
        self,
        plan: Plan,
        reasoning: Optional[ReasoningResult] = None,
        session_id: str = "",
        stop_on_error: bool = True,
    ) -> WorkflowResult:
        """Execute a plan as a workflow.

        Args:
            plan: The execution plan to run.
            reasoning: Optional reasoning result to guide execution.
            session_id: Associated session.
            stop_on_error: Whether to stop on first error.

        Returns:
            WorkflowResult with step results and final output.
        """
        self._execution_count += 1
        start_time = time.monotonic()

        workflow = WorkflowResult(
            plan_id=plan.plan_id,
            session_id=session_id,
            status=WorkflowStatus.RUNNING,
        )
        self._active_workflows[workflow.workflow_id] = workflow

        logger.info(
            f"Workflow [{workflow.workflow_id}] starting",
            extra={"steps": plan.step_count, "plan_id": plan.plan_id},
        )

        try:
            completed_step_ids: List[str] = []

            for step in plan.steps:
                # Execute step
                step_result = await self._execute_step(step, plan, reasoning)

                if step_result.status == StepResultStatus.SUCCESS:
                    completed_step_ids.append(step.step_id)
                elif stop_on_error:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.errors.append({
                        "step_id": step.step_id,
                        "error": step_result.error,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    break

                workflow.step_results.append(step_result)

            # Determine final status
            if workflow.status != WorkflowStatus.FAILED:
                all_success = all(
                    r.status == StepResultStatus.SUCCESS for r in workflow.step_results
                )
                workflow.status = WorkflowStatus.COMPLETED if all_success else WorkflowStatus.FAILED

            workflow.total_duration_seconds = time.monotonic() - start_time
            workflow.final_output = {
                "completed_steps": completed_step_ids,
                "total_steps": plan.step_count,
                "results": [r.output for r in workflow.step_results],
            }

            logger.info(
                f"Workflow [{workflow.workflow_id}] {workflow.status.value}",
                extra={"duration": f"{workflow.total_duration_seconds:.2f}s"},
            )

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.errors.append({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            workflow.total_duration_seconds = time.monotonic() - start_time
            logger.exception(f"Workflow [{workflow.workflow_id}] failed")

        finally:
            self._active_workflows.pop(workflow.workflow_id, None)

        return workflow

    async def _execute_step(
        self,
        step: PlanStep,
        plan: Plan,
        reasoning: Optional[ReasoningResult],
    ) -> StepResult:
        """Execute a single plan step.

        Args:
            step: The plan step to execute.
            plan: The parent plan for context.
            reasoning: Reasoning result for guidance.

        Returns:
            StepResult with execution outcome.
        """
        step_start = time.monotonic()
        logger.debug(f"Executing step: {step.name} [{step.step_id}]")

        result = StepResult(
            step_id=step.step_id,
            step_name=step.name,
            started_at=step_start,
        )

        try:
            # Simulate step execution based on step type
            output = self._process_step(step, plan)
            result.status = StepResultStatus.SUCCESS
            result.output = output

        except Exception as e:
            result.status = StepResultStatus.FAILED
            result.error = str(e)
            logger.error(f"Step [{step.step_id}] failed: {e}")

        result.completed_at = time.monotonic()
        result.duration_seconds = result.completed_at - step_start

        logger.debug(
            f"Step [{step.step_id}] {result.status.value} in {result.duration_seconds:.3f}s",
        )

        return result

    def _process_step(self, step: PlanStep, plan: Plan) -> Any:
        """Process a step based on its type.

        This is where step-type-specific logic would be implemented.
        In future versions, this will route to tool executors.
        """
        if step.step_type.value == "think":
            return {"type": "analysis", "step": step.name, "status": "analysed"}
        elif step.step_type.value == "act":
            return {"type": "action", "step": step.name, "status": "executed"}
        elif step.step_type.value == "observe":
            return {"type": "observation", "step": step.name, "status": "observed"}
        elif step.step_type.value == "verify":
            return {"type": "verification", "step": step.name, "status": "verified"}
        else:
            return {"type": "generic", "step": step.name, "status": "completed"}

    # ── Workflow Management ──

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        workflow = self._active_workflows.get(workflow_id)
        if workflow and workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.CANCELLED
            logger.info(f"Workflow cancelled: {workflow_id}")
            return True
        return False

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Get a workflow result by ID."""
        return self._active_workflows.get(workflow_id)

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            "total_executions": self._execution_count,
            "active_workflows": len(self._active_workflows),
            "active_workflow_ids": list(self._active_workflows.keys()),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get executor summary."""
        return self.get_status()
