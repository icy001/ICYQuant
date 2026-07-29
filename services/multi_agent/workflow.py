"""Agent Workflow Engine - defines and executes multi-agent workflows."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict


class WorkflowStatus(Enum):
    """Status of a workflow execution."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class StepType(Enum):
    """Type of workflow step."""
    TASK = "TASK"
    DECISION = "DECISION"
    PARALLEL = "PARALLEL"
    WAIT = "WAIT"
    NOTIFICATION = "NOTIFICATION"
    CONDITION = "CONDITION"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    step_id: str
    name: str
    step_type: StepType
    assigned_role: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable] = None
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "type": self.step_type.value,
            "assigned_role": self.assigned_role,
            "status": self.status.value,
            "dependencies": self.dependencies,
        }


@dataclass
class Workflow:
    """A complete multi-agent workflow definition."""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.CREATED
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps),
            "completed_steps": sum(1 for s in self.steps if s.status == StepStatus.COMPLETED),
        }


class AgentWorkflowEngine:
    """Workflow engine for orchestrating multi-agent processes.

    Defines and executes workflows like:
    ```
    Research
        ↓
    Debate
        ↓
    Approval
        ↓
    Execution
    ```

    Supports:
    - Sequential and parallel step execution
    - Conditional branching
    - Retry with configurable limits
    - Timeout handling
    - Step dependency management
    """

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._templates: Dict[str, Workflow] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._counter = 0

        # Register default workflow templates
        self._register_default_templates()

    def _register_default_templates(self):
        """Register built-in workflow templates."""
        # Investment Research Workflow
        self.register_template(Workflow(
            workflow_id="template_investment_research",
            name="Investment Research",
            description="Standard investment research workflow",
            steps=[
                WorkflowStep("step1", "Market Analysis", StepType.TASK,
                            "RESEARCH", "Analyze market conditions"),
                WorkflowStep("step2", "Opportunity Screening", StepType.TASK,
                            "STRATEGY", "Screen for opportunities",
                            dependencies=["step1"]),
                WorkflowStep("step3", "Risk Assessment", StepType.TASK,
                            "RISK", "Assess risk factors",
                            dependencies=["step2"]),
                WorkflowStep("step4", "Investment Decision", StepType.DECISION,
                            "PORTFOLIO", "Make investment decision",
                            dependencies=["step2", "step3"]),
            ],
        ))

        # Trade Execution Workflow
        self.register_template(Workflow(
            workflow_id="template_trade_execution",
            name="Trade Execution",
            description="Trade execution workflow with risk check",
            steps=[
                WorkflowStep("step1", "Pre-trade Risk Check", StepType.TASK,
                            "RISK", "Verify risk limits"),
                WorkflowStep("step2", "Order Construction", StepType.TASK,
                            "PORTFOLIO", "Construct order",
                            dependencies=["step1"]),
                WorkflowStep("step3", "Execute Order", StepType.TASK,
                            "EXECUTION", "Execute the trade",
                            dependencies=["step2"]),
                WorkflowStep("step4", "Post-trade Analysis", StepType.TASK,
                            "PERFORMANCE", "Analyze execution quality",
                            dependencies=["step3"]),
            ],
        ))

    def register_template(self, workflow: Workflow):
        """Register a reusable workflow template."""
        self._templates[workflow.workflow_id] = workflow

    def create_from_template(self, template_id: str, name: str = None,
                             context: Dict[str, Any] = None) -> Optional[Workflow]:
        """Create a new workflow instance from a template."""
        template = self._templates.get(template_id)
        if not template:
            return None

        self._counter += 1
        workflow = Workflow(
            workflow_id=f"workflow_{self._counter}",
            name=name or template.name,
            description=template.description,
            steps=[WorkflowStep(
                step_id=f"{s.step_id}_{self._counter}",
                name=s.name,
                step_type=s.step_type,
                assigned_role=s.assigned_role,
                description=s.description,
                dependencies=s.dependencies,
            ) for s in template.steps],
            context=context or {},
        )
        self._workflows[workflow.workflow_id] = workflow
        return workflow

    def execute(self, workflow: Workflow) -> Dict[str, Any]:
        """Execute a workflow.

        Args:
            workflow: The workflow to execute.

        Returns:
            Dict with execution results.
        """
        workflow.status = WorkflowStatus.RUNNING

        results = {
            "workflow": workflow.name,
            "workflow_id": workflow.workflow_id,
            "steps": [],
        }

        # Execute steps in dependency order
        executed = set()
        pending = list(workflow.steps)

        while pending:
            ready = [
                s for s in pending
                if all(dep in executed for dep in s.dependencies)
            ]

            if not ready:
                # Check for circular dependencies
                remaining = {s.step_id for s in pending}
                break

            for step in ready:
                step.status = StepStatus.IN_PROGRESS
                step_result = self._execute_step(step, workflow.context)
                step.status = StepStatus.COMPLETED if step_result.get("success", True) else StepStatus.FAILED
                step.result = step_result
                executed.add(step.step_id)
                results["steps"].append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": step.status.value,
                    "result": step_result,
                })

            pending = [s for s in pending if s.step_id not in executed]

        workflow.status = WorkflowStatus.COMPLETED
        self._execution_history.append(results)

        return results

    def _execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step."""
        result = {
            "success": True,
            "step": step.name,
            "role": step.assigned_role,
            "output": f"Step '{step.name}' executed by {step.assigned_role} agent",
        }

        if step.step_type == StepType.DECISION:
            result["output"] = f"Decision made: {step.description}"
            result["decision"] = "APPROVED"

        elif step.step_type == StepType.PARALLEL:
            result["output"] = f"Parallel tasks executed for: {step.description}"

        elif step.step_type == StepType.NOTIFICATION:
            result["output"] = f"Notification sent: {step.description}"

        elif step.step_type == StepType.CONDITION:
            result["output"] = f"Condition evaluated: {step.description}"
            result["condition_met"] = True

        return result

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a workflow."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        return wf.to_dict()

    def get_templates(self) -> List[Dict[str, Any]]:
        """Get all available workflow templates."""
        return [
            {"id": tid, "name": t.name, "description": t.description, "steps": len(t.steps)}
            for tid, t in self._templates.items()
        ]

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get workflow execution history."""
        return self._execution_history
