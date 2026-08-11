"""Execution Trace — full audit trail for tool call lifecycle.

Pipeline:
    Plan -> Tool Call -> Input -> Output -> Latency -> Decision
        -> ExecutionTrace (step-by-step recording)
        -> Audit Trail
        -> Debugging
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_result import ToolResult

logger = logging.getLogger(__name__)


# ── Enums ──

class TraceStepStatus(str, Enum):
    """Status of a trace step."""

    PLANNED = "planned"
    STARTED = "started"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


# ── TraceStep ──

@dataclass
class TraceStep:
    """A single step in an execution trace."""

    step_id: str = ""
    step_index: int = 0
    tool_name: str = ""
    status: TraceStepStatus = TraceStepStatus.PLANNED

    # ── Input / Output ──
    input_params: Dict[str, Any] = field(default_factory=dict)
    output_data: Any = None
    output_error: Optional[str] = None

    # ── Timing ──
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    latency_ms: float = 0.0

    # ── Decisions ──
    permission_decision: str = ""
    policy_decision: str = ""
    sandbox_decision: str = ""
    cache_hit: bool = False
    retry_count: int = 0

    # ── Context ──
    session_id: str = ""
    agent_id: str = ""
    plan_id: str = ""

    # ── Parent ──
    parent_step_id: Optional[str] = None
    child_step_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step_id,
            "step_index": self.step_index,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "input_params": self.input_params,
            "output_data": self.output_data,
            "output_error": self.output_error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "latency_ms": round(self.latency_ms, 2),
            "permission_decision": self.permission_decision,
            "policy_decision": self.policy_decision,
            "sandbox_decision": self.sandbox_decision,
            "cache_hit": self.cache_hit,
            "retry_count": self.retry_count,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "plan_id": self.plan_id,
            "parent_step_id": self.parent_step_id,
        }


# ── ExecutionTrace ──

@dataclass
class ExecutionTrace:
    """Complete execution trace for an agent session or plan.

    Records every tool call step with full input/output, timing,
    decisions, and context for audit and debugging.

    Supports:
        - Step-by-step recording
        - Timing tracking
        - Decision logging
        - Parent-child step relationships
        - Serialization for audit

    Usage:
        trace = ExecutionTrace(session_id="s1", agent_id="a1")
        trace.start_step("backtest.run", {"strategy_id": "s1"})
        # ... execution ...
        trace.complete_step(result)
        trace.to_dict()  # Full audit trail
    """

    trace_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    plan_id: str = ""

    steps: List[TraceStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_latency_ms: float = 0.0

    # ── Counters ──
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0

    # ── Metadata ──
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Step success rate."""
        if self.total_steps == 0:
            return 0.0
        return self.successful_steps / self.total_steps

    # ── Step Lifecycle ──

    def start_step(
        self,
        tool_name: str,
        params: Dict[str, Any],
        parent_step_id: Optional[str] = None,
    ) -> TraceStep:
        """Start a new trace step.

        Args:
            tool_name: The tool being called.
            params: Input parameters.
            parent_step_id: Optional parent step.

        Returns:
            The created TraceStep.
        """
        from uuid import uuid4

        step = TraceStep(
            step_id=uuid4().hex,
            step_index=len(self.steps),
            tool_name=tool_name,
            status=TraceStepStatus.STARTED,
            input_params=params,
            started_at=datetime.now(timezone.utc),
            parent_step_id=parent_step_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            plan_id=self.plan_id,
        )

        if parent_step_id:
            parent = self._find_step(parent_step_id)
            if parent:
                parent.child_step_ids.append(step.step_id)

        self.steps.append(step)
        self.total_steps += 1

        logger.debug(f"Trace step started: {step.step_id} ({tool_name})")
        return step

    def complete_step(
        self,
        step_id: str,
        result: ToolResult,
        permission_decision: str = "",
        policy_decision: str = "",
        sandbox_decision: str = "",
    ) -> None:
        """Complete a trace step with the execution result.

        Args:
            step_id: The step identifier.
            result: The tool execution result.
            permission_decision: Permission check result.
            policy_decision: Policy check result.
            sandbox_decision: Sandbox check result.
        """
        step = self._find_step(step_id)
        if step is None:
            logger.warning(f"Trace step not found: {step_id}")
            return

        step.status = TraceStepStatus.COMPLETED if result.success else TraceStepStatus.FAILED
        step.completed_at = datetime.now(timezone.utc)
        step.latency_ms = result.latency_ms
        step.output_data = result.data
        step.output_error = result.error
        step.permission_decision = permission_decision
        step.policy_decision = policy_decision
        step.sandbox_decision = sandbox_decision
        step.cache_hit = result.from_cache
        step.retry_count = result.attempt - 1 if result.attempt > 1 else 0

        if result.success:
            self.successful_steps += 1
        else:
            self.failed_steps += 1

        logger.debug(
            f"Trace step completed: {step_id} status={step.status.value} "
            f"({step.latency_ms:.0f}ms)"
        )

    def skip_step(self, step_id: str, reason: str = "") -> None:
        """Mark a step as skipped.

        Args:
            step_id: The step identifier.
            reason: Skip reason.
        """
        step = self._find_step(step_id)
        if step:
            step.status = TraceStepStatus.SKIPPED
            step.output_error = reason
            self.skipped_steps += 1

    def cancel_step(self, step_id: str, reason: str = "") -> None:
        """Cancel an active step.

        Args:
            step_id: The step identifier.
            reason: Cancel reason.
        """
        step = self._find_step(step_id)
        if step:
            step.status = TraceStepStatus.CANCELLED
            step.output_error = reason

    # ── Trace Completion ──

    def finalize(self) -> None:
        """Finalize the trace, computing totals."""
        self.completed_at = datetime.now(timezone.utc)
        self.total_latency_ms = (
            (self.completed_at - self.started_at).total_seconds() * 1000
        )
        logger.info(
            f"Trace finalized: {self.trace_id}, "
            f"{self.total_steps} steps, "
            f"success_rate={self.success_rate:.1%}"
        )

    # ── Queries ──

    def get_failed_steps(self) -> List[TraceStep]:
        """Get all failed steps."""
        return [s for s in self.steps if s.status == TraceStepStatus.FAILED]

    def get_slow_steps(self, threshold_ms: float = 5000.0) -> List[TraceStep]:
        """Get steps exceeding a latency threshold.

        Args:
            threshold_ms: Latency threshold in milliseconds.

        Returns:
            List of slow steps.
        """
        return [s for s in self.steps if s.latency_ms > threshold_ms]

    def get_step_by_tool(self, tool_name: str) -> List[TraceStep]:
        """Get all steps for a specific tool.

        Args:
            tool_name: The tool name.

        Returns:
            List of matching steps.
        """
        return [s for s in self.steps if s.tool_name == tool_name]

    # ── Private Methods ──

    def _find_step(self, step_id: str) -> Optional[TraceStep]:
        """Find a step by ID.

        Args:
            step_id: The step identifier.

        Returns:
            The TraceStep, or None.
        """
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full trace to dictionary."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "plan_id": self.plan_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "success_rate": round(self.success_rate, 4),
            "tags": self.tags,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_audit_report(self) -> Dict[str, Any]:
        """Generate an audit-friendly report."""
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "duration_ms": round(self.total_latency_ms, 2),
            "total_steps": self.total_steps,
            "successful": self.successful_steps,
            "failed": self.failed_steps,
            "failed_details": [
                {
                    "tool": s.tool_name,
                    "error": s.output_error,
                    "latency_ms": round(s.latency_ms, 2),
                }
                for s in self.get_failed_steps()
            ],
            "slow_steps": [
                {
                    "tool": s.tool_name,
                    "latency_ms": round(s.latency_ms, 2),
                }
                for s in self.get_slow_steps()
            ],
        }
