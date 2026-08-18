"""
ICYQuant Platform - Workflow Engine

Supports multi-step workflows with approval, pause, resume, and retry.
Orchestrates complex sequences like research → backtest → deploy → production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    APPROVAL_REQUIRED = "approval_required"


@dataclass
class WorkflowStep:
    name: str
    action: str
    handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approval_from: str = "admin"
    timeout_seconds: int = 300
    retries: int = 0
    current_retry: int = 0
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "action": self.action,
            "status": self.status.value,
            "requiresApproval": self.requires_approval,
            "retries": self.retries,
            "currentRetry": self.current_retry,
            "result": self.result,
            "error": self.error_message,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Workflow:
    name: str
    steps: List[WorkflowStep] = field(default_factory=list)
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_index: int = 0
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.workflow_id,
            "name": self.name,
            "status": self.status.value,
            "currentStep": self.current_step_index,
            "steps": [s.to_dict() for s in self.steps],
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "error": self.error_message,
        }


class WorkflowEngine:
    """
    Multi-step workflow engine with approval and retry support.

    Manages workflow lifecycle: create → run → approve → complete/fail.
    Supports pause/resume for long-running workflows.
    """

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._templates: Dict[str, List[Dict[str, Any]]] = {}
        self._approval_callbacks: Dict[str, Callable] = {}
        self._completed_log: List[Workflow] = []
        self._max_completed_log = 500

    def create_workflow(
        self,
        name: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        template: Optional[str] = None,
        created_by: str = "system",
        context: Optional[Dict[str, Any]] = None,
    ) -> Workflow:
        if steps is None and template:
            steps = self._templates.get(template, [])
        if not steps:
            raise ValueError("Workflow must have steps or a valid template")

        workflow_steps = []
        for step_def in steps:
            workflow_steps.append(WorkflowStep(
                name=step_def.get("name", ""),
                action=step_def.get("action", ""),
                handler=step_def.get("handler"),
                parameters=step_def.get("parameters", {}),
                requires_approval=step_def.get("requires_approval", False),
                approval_from=step_def.get("approval_from", "admin"),
                timeout_seconds=step_def.get("timeout_seconds", 300),
                retries=step_def.get("retries", 0),
            ))

        workflow = Workflow(
            name=name,
            steps=workflow_steps,
            created_by=created_by,
            context=context or {},
        )
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Workflow created: {name} ({workflow.workflow_id})")
        return workflow

    def register_template(
        self,
        template_name: str,
        steps: List[Dict[str, Any]],
    ):
        self._templates[template_name] = steps
        logger.info(f"Workflow template registered: {template_name}")

    def start_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        if wf.status not in (WorkflowStatus.PENDING, WorkflowStatus.PAUSED):
            return False

        wf.status = WorkflowStatus.RUNNING
        wf.updated_at = datetime.now()
        logger.info(f"Workflow started: {wf.name}")
        return self._execute_next_step(wf)

    def _execute_next_step(self, wf: Workflow) -> bool:
        if wf.current_step_index >= len(wf.steps):
            wf.status = WorkflowStatus.COMPLETED
            wf.updated_at = datetime.now()
            self._archive_workflow(wf)
            logger.info(f"Workflow completed: {wf.name}")
            return True

        step = wf.steps[wf.current_step_index]

        if step.status == WorkflowStatus.COMPLETED:
            wf.current_step_index += 1
            return self._execute_next_step(wf)

        if step.requires_approval and step.status != WorkflowStatus.COMPLETED:
            step.status = WorkflowStatus.APPROVAL_REQUIRED
            wf.status = WorkflowStatus.APPROVAL_REQUIRED
            wf.updated_at = datetime.now()
            logger.info(f"Workflow '{wf.name}' awaiting approval for step '{step.name}'")
            return True

        step.status = WorkflowStatus.RUNNING
        step.started_at = datetime.now()

        if step.handler:
            try:
                result = step.handler(step.parameters)
                step.result = result
                step.status = WorkflowStatus.COMPLETED
                step.completed_at = datetime.now()
                wf.current_step_index += 1
                wf.updated_at = datetime.now()
                logger.info(f"Step completed: {step.name}")
                return self._execute_next_step(wf)
            except Exception as e:
                step.current_retry += 1
                if step.current_retry < step.retries:
                    step.status = WorkflowStatus.PENDING
                    logger.warning(
                        f"Step '{step.name}' failed (retry {step.current_retry}/{step.retries})"
                    )
                    return self._execute_next_step(wf)
                else:
                    step.status = WorkflowStatus.FAILED
                    step.error_message = str(e)
                    wf.status = WorkflowStatus.FAILED
                    wf.error_message = str(e)
                    wf.updated_at = datetime.now()
                    logger.error(f"Workflow failed: {wf.name} - {e}")
                    return False
        else:
            step.status = WorkflowStatus.COMPLETED
            step.completed_at = datetime.now()
            wf.current_step_index += 1
            wf.updated_at = datetime.now()
            return self._execute_next_step(wf)

    def approve_step(self, workflow_id: str, approver: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False

        step = wf.steps[wf.current_step_index]
        if step.status != WorkflowStatus.APPROVAL_REQUIRED:
            return False

        step.status = WorkflowStatus.PENDING
        step.requires_approval = False  # Clear approval requirement after approval
        wf.status = WorkflowStatus.RUNNING
        wf.updated_at = datetime.now()
        logger.info(
            f"Step '{step.name}' approved by {approver} in workflow '{wf.name}'"
        )
        return self._execute_next_step(wf)

    def pause_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf or wf.status != WorkflowStatus.RUNNING:
            return False
        wf.status = WorkflowStatus.PAUSED
        wf.updated_at = datetime.now()
        logger.info(f"Workflow paused: {wf.name}")
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf or wf.status != WorkflowStatus.PAUSED:
            return False
        wf.status = WorkflowStatus.RUNNING
        wf.updated_at = datetime.now()
        logger.info(f"Workflow resumed: {wf.name}")
        return self._execute_next_step(wf)

    def cancel_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            # Check if it's already completed and still in the completed log
            for w in self._completed_log:
                if w.workflow_id == workflow_id:
                    return False  # Already completed, can't cancel
            return False  # Not found
        wf.status = WorkflowStatus.CANCELLED
        wf.updated_at = datetime.now()
        self._archive_workflow(wf)
        logger.info(f"Workflow cancelled: {wf.name}")
        return True

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        wf = self._workflows.get(workflow_id)
        if wf is not None:
            return wf
        # Also check completed log
        for w in self._completed_log:
            if w.workflow_id == workflow_id:
                return w
        return None

    def list_active(self) -> List[Workflow]:
        return [
            wf for wf in self._workflows.values()
            if wf.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED, WorkflowStatus.APPROVAL_REQUIRED)
        ]

    def list_templates(self) -> List[str]:
        return list(self._templates.keys())

    def _archive_workflow(self, wf: Workflow):
        self._completed_log.append(wf)
        if len(self._completed_log) > self._max_completed_log:
            self._completed_log = self._completed_log[-self._max_completed_log:]
        # Only remove from active tracking if it's in a terminal state
        if wf.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
            # Keep it accessible via get_workflow but not in active list
            pass

    def get_status(self) -> Dict:
        active = self.list_active()
        return {
            "totalActive": len(active),
            "running": sum(1 for w in active if w.status == WorkflowStatus.RUNNING),
            "paused": sum(1 for w in active if w.status == WorkflowStatus.PAUSED),
            "awaitingApproval": sum(1 for w in active if w.status == WorkflowStatus.APPROVAL_REQUIRED),
            "templates": len(self._templates),
            "completed": len(self._completed_log),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
