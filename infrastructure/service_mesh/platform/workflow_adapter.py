"""Workflow Engine Adapter for the Service Mesh Platform.

Provides ``WorkflowAdapter`` for integrating the Workflow Engine
with the service mesh for task scheduling, service orchestration,
and long transaction execution.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class WorkflowAdapter:
    """Adapter for integrating Workflow Engine with the mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._workflow_handlers: Dict[str, Callable] = {}
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
        self._adapter_active = False
        self._workflow_count = 0

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the workflow adapter."""
        self._adapter_active = True
        self._telemetry.log_platform_event(
            "workflow_adapter_initialized", "workflow",
        )
        logger.info("Workflow adapter initialized.")
        return {"success": True}

    async def shutdown(self) -> Dict[str, Any]:
        """Shutdown the workflow adapter."""
        self._adapter_active = False
        self._telemetry.log_platform_event(
            "workflow_adapter_shutdown", "workflow",
        )
        logger.info("Workflow adapter shut down.")
        return {"success": True}

    @property
    def is_active(self) -> bool:
        return self._adapter_active

    def register_workflow_handler(
        self,
        workflow_type: str,
        handler: Callable,
    ) -> None:
        self._workflow_handlers[workflow_type] = handler

    async def execute_workflow(
        self,
        workflow_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a workflow through the mesh."""
        self._workflow_count += 1
        workflow_id = f"wf-{int(time.monotonic())}"

        handler = self._workflow_handlers.get(workflow_type)
        if handler is None:
            return {
                "success": False,
                "error": f"No handler for workflow: {workflow_type}",
            }

        self._active_workflows[workflow_id] = {
            "workflow_type": workflow_type,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "params": params,
        }

        try:
            result = handler(params)
            if asyncio.iscoroutine(result):
                result = await result

            self._active_workflows[workflow_id]["status"] = "completed"
            self._active_workflows[workflow_id][
                "completed_at"
            ] = datetime.utcnow().isoformat()
        except Exception as exc:
            self._active_workflows[workflow_id]["status"] = "failed"
            self._active_workflows[workflow_id][
                "error"
            ] = str(exc)
            self._telemetry.log_error(
                "workflow_adapter",
                "workflow_failed",
                str(exc),
                {"workflow_type": workflow_type},
            )
            return {
                "success": False,
                "error": str(exc),
                "workflow_id": workflow_id,
            }

        self._telemetry.log_platform_event(
            "workflow_executed",
            "workflow",
            {"workflow_type": workflow_type,
             "workflow_id": workflow_id},
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "result": result,
        }

    async def schedule_task(
        self,
        task_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Schedule a task through the workflow engine."""
        return await self.execute_workflow(
            task_name, params
        )

    async def orchestrate_services(
        self,
        service_graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Orchestrate multiple services."""
        return {
            "success": True,
            "orchestration_id": f"orch-{int(time.monotonic())}",
            "services": list(service_graph.keys()),
        }

    async def execute_long_transaction(
        self,
        transaction_id: str,
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute a long transaction."""
        results: List[Dict[str, Any]] = []
        for step in steps:
            handler = self._workflow_handlers.get(
                step.get("type", "")
            )
            if handler:
                try:
                    result = handler(step)
                    if asyncio.iscoroutine(result):
                        result = await result
                    results.append(result)
                except Exception as exc:
                    results.append({
                        "success": False,
                        "error": str(exc),
                    })
                    return {
                        "success": False,
                        "transaction_id": transaction_id,
                        "results": results,
                        "error": str(exc),
                    }

        return {
            "success": True,
            "transaction_id": transaction_id,
            "results": results,
        }

    def list_active_workflows(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        workflows = list(self._active_workflows.values())
        if status:
            workflows = [
                w for w in workflows
                if w.get("status") == status
            ]
        return workflows[-20:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": self._adapter_active,
                "workflow_count": self._workflow_count,
                "active_workflows": len(self._active_workflows),
                "handler_count": len(self._workflow_handlers),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"WorkflowAdapter(active={self._adapter_active})"
            )
