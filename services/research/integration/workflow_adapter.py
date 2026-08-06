"""Workflow Adapter — bridges Research Platform to the Workflow Engine.

Commit 11 Part 1.5: Integrates research tasks as workflows and pipelines
within ICYQuant's Workflow Engine.

Architecture::

    Research Task → Workflow → Pipeline → Research Result

Supported workflows:
    - Experiment Workflow
    - Factor Workflow
    - Backtest Workflow
    - Portfolio Workflow
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class WorkflowAdapterState(str, Enum):
    """Workflow adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ResearchWorkflowType(str, Enum):
    """Supported research workflow types."""

    EXPERIMENT = "experiment"
    FACTOR = "factor"
    BACKTEST = "backtest"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"


class WorkflowAdapter:
    """Adapter for integrating Research Platform with Workflow Engine.

    Converts research tasks into workflow definitions, manages workflow
    execution, and reports results back to the research platform.

    Usage::

        adapter = WorkflowAdapter(config={"workflow_engine_url": "..."})
        await adapter.initialize()
        wf_id = await adapter.create_workflow(
            workflow_type=ResearchWorkflowType.BACKTEST,
            params={"dataset": "us_equity_daily", "strategy": "momentum"},
        )
        result = await adapter.execute_workflow(wf_id)
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"wfa-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: WorkflowAdapterState = WorkflowAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Workflow Engine connection
        self._engine_url: str = self._config.get("workflow_engine_url", "http://localhost:8100")
        self._engine_connected: bool = False

        # Active workflows
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
        self._workflow_definitions: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> WorkflowAdapterState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._engine_connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the workflow adapter and connect to Workflow Engine."""
        self._state = WorkflowAdapterState.INITIALIZING
        logger.info("Initializing WorkflowAdapter [%s] → %s", self._id, self._engine_url)

        try:
            await self._connect()
            self._engine_connected = True
            self._state = WorkflowAdapterState.CONNECTED
        except Exception as exc:
            logger.error("Failed to connect to Workflow Engine: %s", exc)
            self._state = WorkflowAdapterState.ERROR
            raise

        # Register default workflow templates
        await self._register_default_workflows()
        logger.info("WorkflowAdapter initialized [%s]", self._id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with the Workflow Engine."""
        status: Dict[str, Any] = {
            "adapter_id": self._id,
            "engine_connected": self._engine_connected,
            "active_workflows": len(self._active_workflows),
        }
        if not self._engine_connected:
            try:
                await self._connect()
                self._engine_connected = True
                status["reconnected"] = True
            except Exception:
                status["reconnected"] = False
        return status

    async def shutdown(self) -> None:
        """Disconnect from Workflow Engine and clean up."""
        logger.info("Shutting down WorkflowAdapter [%s]...", self._id)
        self._active_workflows.clear()
        self._workflow_definitions.clear()
        self._engine_connected = False
        self._state = WorkflowAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish connection to Workflow Engine."""
        # Placeholder for actual gRPC/HTTP connection
        logger.info("Connecting to Workflow Engine at %s", self._engine_url)
        await asyncio.sleep(0.01)  # simulate connection
        logger.info("Connected to Workflow Engine")

    async def _register_default_workflows(self) -> None:
        """Register default research workflow templates."""
        for wf_type in ResearchWorkflowType:
            self._workflow_definitions[wf_type.value] = {
                "type": wf_type.value,
                "version": "1.0",
                "steps": self._get_default_steps(wf_type),
            }

    def _get_default_steps(self, wf_type: ResearchWorkflowType) -> List[Dict[str, Any]]:
        """Return default pipeline steps for each workflow type."""
        if wf_type == ResearchWorkflowType.EXPERIMENT:
            return [
                {"step": "load_dataset", "order": 1},
                {"step": "preprocess", "order": 2},
                {"step": "train", "order": 3},
                {"step": "evaluate", "order": 4},
                {"step": "report", "order": 5},
            ]
        elif wf_type == ResearchWorkflowType.FACTOR:
            return [
                {"step": "load_data", "order": 1},
                {"step": "compute_factor", "order": 2},
                {"step": "normalize", "order": 3},
                {"step": "evaluate_ic", "order": 4},
                {"step": "publish", "order": 5},
            ]
        elif wf_type == ResearchWorkflowType.BACKTEST:
            return [
                {"step": "load_dataset", "order": 1},
                {"step": "initialize_strategy", "order": 2},
                {"step": "run_simulation", "order": 3},
                {"step": "compute_metrics", "order": 4},
                {"step": "generate_report", "order": 5},
            ]
        elif wf_type == ResearchWorkflowType.PORTFOLIO:
            return [
                {"step": "load_alpha_pool", "order": 1},
                {"step": "build_portfolio", "order": 2},
                {"step": "optimize", "order": 3},
                {"step": "risk_analysis", "order": 4},
                {"step": "generate_report", "order": 5},
            ]
        else:
            return []

    # ------------------------------------------------------------------
    # Workflow Operations
    # ------------------------------------------------------------------

    async def create_workflow(
        self,
        workflow_type: ResearchWorkflowType,
        params: Optional[Dict[str, Any]] = None,
        *,
        workflow_name: Optional[str] = None,
    ) -> str:
        """Create a new research workflow.

        Args:
            workflow_type: Type of research workflow.
            params: Workflow parameters.
            workflow_name: Optional display name.

        Returns:
            Workflow ID.
        """
        if not self._engine_connected:
            raise RuntimeError("Not connected to Workflow Engine")

        wf_id = f"wf-{uuid4().hex[:16]}"
        definition = self._workflow_definitions.get(workflow_type.value, {})
        workflow = {
            "id": wf_id,
            "name": workflow_name or f"{workflow_type.value}-{wf_id[:8]}",
            "type": workflow_type.value,
            "definition": definition,
            "params": params or {},
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._active_workflows[wf_id] = workflow
        logger.info("Workflow created: %s [%s]", wf_id, workflow_type.value)
        return wf_id

    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute a research workflow and return results.

        Args:
            workflow_id: The workflow ID to execute.

        Returns:
            Execution results.
        """
        workflow = self._active_workflows.get(workflow_id)
        if workflow is None:
            raise KeyError(f"Workflow not found: {workflow_id}")

        workflow["status"] = "running"
        workflow["started_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Executing workflow: %s", workflow_id)

        # Execute pipeline steps
        steps = workflow.get("definition", {}).get("steps", [])
        results: Dict[str, Any] = {"workflow_id": workflow_id, "steps": {}}
        for step in sorted(steps, key=lambda s: s.get("order", 0)):
            try:
                step_result = await self._execute_step(step, workflow.get("params", {}))
                results["steps"][step["step"]] = {"status": "completed", "result": step_result}
            except Exception as exc:
                results["steps"][step["step"]] = {"status": "failed", "error": str(exc)}
                workflow["status"] = "failed"
                break
        else:
            workflow["status"] = "completed"

        workflow["completed_at"] = datetime.now(timezone.utc).isoformat()
        workflow["results"] = results
        logger.info("Workflow %s completed: %s", workflow_id, workflow["status"])
        return results

    async def _execute_step(self, step: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step (stub — actual execution delegated to engine)."""
        logger.debug("Executing step: %s", step["step"])
        await asyncio.sleep(0.01)  # simulate step execution
        return {"step": step["step"], "params_used": list(params.keys())}

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a workflow."""
        workflow = self._active_workflows.get(workflow_id)
        if workflow is None:
            raise KeyError(f"Workflow not found: {workflow_id}")
        return {"id": workflow_id, "status": workflow["status"], "type": workflow["type"]}

    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow."""
        workflow = self._active_workflows.get(workflow_id)
        if workflow is None:
            raise KeyError(f"Workflow not found: {workflow_id}")
        workflow["status"] = "cancelled"
        logger.info("Workflow cancelled: %s", workflow_id)
