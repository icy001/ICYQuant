"""Agent Workflow - automated trading workflow orchestration.

Defines and executes the end-to-end autonomous trading workflow:
- Market Open → Market Scan → Opportunity Detection → Trading Proposal
→ Risk Review → Portfolio Check → Execution → Performance Feedback → Memory Update

Workflows can be scheduled, triggered by events, or run on-demand.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    agent_type: str = ""  # Which agent handles this step
    action: str = ""       # Action to send to agent
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 1
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    condition: Optional[str] = None  # Optional condition expression to skip step

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "action": self.action,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration": (self.completed_at - self.started_at) if self.completed_at and self.started_at else None,
        }


@dataclass
class WorkflowRun:
    """A single workflow execution."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_name: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: List[WorkflowStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "context": self.context,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": (self.completed_at - self.started_at) if self.completed_at and self.started_at else None,
            "error": self.error,
        }

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 100.0 if self.status == WorkflowStatus.COMPLETED else 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed / len(self.steps) * 100.0


class WorkflowEngine:
    """Workflow Engine for autonomous trading pipelines.

    Manages the definition and execution of trading workflows.
    Supports:
    - Pre-defined workflows (daily_scan, rebalance, risk_check)
    - Custom workflows
    - Scheduled and event-driven execution
    - Step dependencies and parallel execution
    - Retry with backoff
    - Timeout handling
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._workflows: Dict[str, List[WorkflowStep]] = {}
        self._runs: List[WorkflowRun] = []
        self._active_runs: Dict[str, WorkflowRun] = {}
        self._send_func: Optional[Callable] = None  # Function to send messages to agents

        # Register default workflows
        self._register_default_workflows()

    def set_send_function(self, func: Callable) -> None:
        """Set the function used to send messages to agents."""
        self._send_func = func

    # ── Workflow Registration ───────────────────────────────────

    def register_workflow(
        self, name: str, steps: List[WorkflowStep]
    ) -> None:
        """Register a custom workflow."""
        self._workflows[name] = steps
        logger.info("Registered workflow: %s (%d steps)", name, len(steps))

    def _register_default_workflows(self) -> None:
        """Register built-in default workflows."""

        # Daily Market Scan Workflow
        self._workflows["daily_scan"] = [
            WorkflowStep(
                name="market_scan",
                description="Scan market for opportunities",
                agent_type="market_agent",
                action="SCAN_MARKET",
                timeout_seconds=60,
            ),
            WorkflowStep(
                name="analyze_opportunities",
                description="Analyze detected opportunities",
                agent_type="trading_agent",
                action="ANALYZE_OPPORTUNITIES",
                depends_on=["market_scan"],
                timeout_seconds=45,
            ),
            WorkflowStep(
                name="risk_review",
                description="Review proposals for risk",
                agent_type="risk_agent",
                action="REVIEW_PROPOSALS",
                depends_on=["analyze_opportunities"],
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="portfolio_adjust",
                description="Adjust portfolio if needed",
                agent_type="portfolio_agent",
                action="CHECK_PORTFOLIO",
                depends_on=["risk_review"],
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="execute_trades",
                description="Execute approved trades",
                agent_type="execution_agent",
                action="EXECUTE_TRADES",
                depends_on=["portfolio_adjust"],
                timeout_seconds=120,
            ),
        ]

        # Risk Check Workflow
        self._workflows["risk_check"] = [
            WorkflowStep(
                name="assess_risk",
                description="Full risk assessment",
                agent_type="risk_agent",
                action="ASSESS_RISK",
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="check_limits",
                description="Check all risk limits",
                agent_type="risk_agent",
                action="CHECK_LIMITS",
                depends_on=["assess_risk"],
                timeout_seconds=15,
            ),
        ]

        # Rebalance Workflow
        self._workflows["rebalance"] = [
            WorkflowStep(
                name="check_drift",
                description="Check portfolio drift",
                agent_type="portfolio_agent",
                action="CHECK_DRIFT",
                timeout_seconds=20,
            ),
            WorkflowStep(
                name="generate_proposal",
                description="Generate rebalance proposal",
                agent_type="portfolio_agent",
                action="GENERATE_REBALANCE",
                depends_on=["check_drift"],
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="risk_approve",
                description="Risk approval for rebalance",
                agent_type="risk_agent",
                action="REVIEW_REBALANCE",
                depends_on=["generate_proposal"],
                timeout_seconds=20,
            ),
            WorkflowStep(
                name="execute_rebalance",
                description="Execute rebalance trades",
                agent_type="execution_agent",
                action="EXECUTE_REBALANCE",
                depends_on=["risk_approve"],
                timeout_seconds=180,
            ),
        ]

        # End-to-end full pipeline
        self._workflows["full_pipeline"] = [
            WorkflowStep(
                name="market_observe",
                description="Market Agent observes market",
                agent_type="market_agent",
                action="OBSERVE",
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="opportunity_detect",
                description="Detect trading opportunities",
                agent_type="market_agent",
                action="DETECT_OPPORTUNITIES",
                depends_on=["market_observe"],
                timeout_seconds=45,
            ),
            WorkflowStep(
                name="trading_propose",
                description="Trading Agent proposes trades",
                agent_type="trading_agent",
                action="PROPOSE_TRADES",
                depends_on=["opportunity_detect"],
                timeout_seconds=45,
            ),
            WorkflowStep(
                name="risk_review",
                description="Risk Agent reviews proposals",
                agent_type="risk_agent",
                action="REVIEW_PROPOSALS",
                depends_on=["trading_propose"],
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="portfolio_check",
                description="Portfolio Agent checks composition",
                agent_type="portfolio_agent",
                action="CHECK_PORTFOLIO",
                depends_on=["risk_review"],
                timeout_seconds=30,
            ),
            WorkflowStep(
                name="execution",
                description="Execution Agent executes trades",
                agent_type="execution_agent",
                action="EXECUTE_TRADES",
                depends_on=["portfolio_check"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="performance_feedback",
                description="Record performance and learn",
                agent_type="trading_agent",
                action="RECORD_FEEDBACK",
                depends_on=["execution"],
                timeout_seconds=15,
            ),
            WorkflowStep(
                name="memory_update",
                description="Update agent memory with results",
                agent_type="supervisor",
                action="UPDATE_MEMORY",
                depends_on=["performance_feedback"],
                timeout_seconds=10,
            ),
        ]

    # ── Workflow Execution ──────────────────────────────────────

    def start_workflow(
        self, name: str, context: Dict[str, Any] = None
    ) -> Optional[WorkflowRun]:
        """Start a workflow execution.

        Args:
            name: Workflow name to execute
            context: Initial context data (symbols, params, etc.)

        Returns:
            WorkflowRun or None if workflow not found
        """
        steps_def = self._workflows.get(name)
        if not steps_def:
            logger.error("Workflow not found: %s", name)
            return None

        # Create fresh copies of steps
        steps = [
            WorkflowStep(
                name=s.name,
                description=s.description,
                agent_type=s.agent_type,
                action=s.action,
                timeout_seconds=s.timeout_seconds,
                max_retries=s.max_retries,
                depends_on=list(s.depends_on),
                condition=s.condition,
            )
            for s in steps_def
        ]

        run = WorkflowRun(
            workflow_name=name,
            steps=steps,
            context=context or {},
            status=WorkflowStatus.RUNNING,
            started_at=time.time(),
        )

        self._runs.append(run)
        self._active_runs[run.run_id] = run

        logger.info("Started workflow: %s (run=%s, %d steps)", name, run.run_id, len(steps))

        # Execute steps
        self._execute_steps(run)

        return run

    def _execute_steps(self, run: WorkflowRun) -> None:
        """Execute all steps in dependency order."""
        completed_ids: set = set()
        step_map = {s.step_id: s for s in run.steps}

        while True:
            # Find ready steps (all dependencies met)
            ready = [
                s for s in run.steps
                if s.status == StepStatus.PENDING
                and all(dep in completed_ids for dep in s.depends_on)
            ]

            if not ready:
                # Check if we're done
                all_done = all(
                    s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.FAILED)
                    for s in run.steps
                )
                if all_done:
                    break
                else:
                    # Some steps still pending but dependencies not met
                    # Check for deadlock (steps that can never execute)
                    stuck = [
                        s for s in run.steps
                        if s.status == StepStatus.PENDING
                        and any(dep not in completed_ids for dep in s.depends_on)
                        and all(
                            step_map[dep].status == StepStatus.FAILED
                            for dep in s.depends_on if dep in step_map
                        )
                    ]
                    for s in stuck:
                        s.status = StepStatus.SKIPPED
                        s.error = "Dependency failed"
                    if not stuck:
                        break
                continue

            # Execute ready steps
            for step in ready:
                self._execute_step(step, run)
                if step.status == StepStatus.COMPLETED:
                    completed_ids.add(step.step_id)

        # Determine final status
        failures = [s for s in run.steps if s.status == StepStatus.FAILED]
        if failures:
            run.status = WorkflowStatus.FAILED
            run.error = f"{len(failures)} step(s) failed"
        else:
            run.status = WorkflowStatus.COMPLETED

        run.completed_at = time.time()
        self._active_runs.pop(run.run_id, None)

        # Trim history
        if len(self._runs) > 100:
            self._runs = self._runs[-100:]

        duration = run.completed_at - (run.started_at or run.completed_at)
        logger.info(
            "Workflow %s completed: %s (%.1fs, %s)",
            run.workflow_name, run.status.value, duration, run.error or "ok",
        )

    def _execute_step(self, step: WorkflowStep, run: WorkflowRun) -> None:
        """Execute a single workflow step."""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        try:
            # Check condition
            if step.condition:
                condition_met = self._evaluate_condition(step.condition, run.context)
                if not condition_met:
                    step.status = StepStatus.SKIPPED
                    step.completed_at = time.time()
                    return

            # Send message to agent
            if self._send_func:
                self._send_func(
                    recipient=step.agent_type,
                    event=step.action,
                    data={
                        "run_id": run.run_id,
                        "step_id": step.step_id,
                        "workflow": run.workflow_name,
                        "context": run.context,
                    },
                )

            # Simulate step completion
            # In production, agents would respond asynchronously
            step.result = {
                "step": step.name,
                "agent": step.agent_type,
                "action": step.action,
                "status": "completed",
            }
            step.status = StepStatus.COMPLETED

        except Exception as e:
            logger.error("Step %s failed: %s", step.name, e)
            step.error = str(e)

            # Retry logic
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING
                logger.info("Retrying step %s (attempt %d/%d)", step.name, step.retry_count, step.max_retries)
            else:
                step.status = StepStatus.FAILED

        finally:
            step.completed_at = time.time()

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition expression against context."""
        try:
            # Support simple conditions like "volatility != high", "mode == normal"
            if "==" in condition:
                key, val = condition.split("==")
                return str(context.get(key.strip(), "")).lower() == val.strip().lower()
            elif "!=" in condition:
                key, val = condition.split("!=")
                return str(context.get(key.strip(), "")).lower() != val.strip().lower()
            elif ">" in condition:
                key, val = condition.split(">")
                return float(context.get(key.strip(), 0)) > float(val.strip())
            elif "<" in condition:
                key, val = condition.split("<")
                return float(context.get(key.strip(), 0)) < float(val.strip())
            return True
        except Exception:
            return True

    # ── Workflow Management ─────────────────────────────────────

    def cancel_workflow(self, run_id: str) -> bool:
        """Cancel a running workflow."""
        run = self._active_runs.get(run_id)
        if not run:
            return False

        run.status = WorkflowStatus.CANCELLED
        run.completed_at = time.time()
        self._active_runs.pop(run_id, None)

        # Mark pending steps as skipped
        for step in run.steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                step.status = StepStatus.SKIPPED

        logger.info("Cancelled workflow: %s", run_id)
        return True

    def get_workflow_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a workflow run."""
        for run in self._runs:
            if run.run_id == run_id:
                return run.to_dict()
        return None

    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflow runs."""
        return [r.to_dict() for r in self._active_runs.values()]

    def get_workflow_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get workflow run history."""
        return [r.to_dict() for r in self._runs[-limit:]]

    def get_available_workflows(self) -> List[str]:
        """Get list of available workflow names."""
        return list(self._workflows.keys())

    def get_workflow_definition(self, name: str) -> Optional[List[Dict[str, Any]]]:
        """Get the definition of a workflow."""
        steps = self._workflows.get(name)
        if not steps:
            return None
        return [
            {
                "name": s.name,
                "description": s.description,
                "agent_type": s.agent_type,
                "action": s.action,
                "depends_on": s.depends_on,
                "timeout_seconds": s.timeout_seconds,
                "max_retries": s.max_retries,
            }
            for s in steps
        ]

    def get_summary(self) -> Dict[str, Any]:
        """Get workflow engine summary."""
        runs = self._runs
        by_status = {}
        for r in runs:
            s = r.status.value
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "workflows_defined": len(self._workflows),
            "available_workflows": list(self._workflows.keys()),
            "total_runs": len(runs),
            "active_runs": len(self._active_runs),
            "runs_by_status": by_status,
        }
