"""Workflow Tools — platform adapter for Workflow Engine operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Workflow Engine for DAG-based task orchestration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput
from services.ai_agent.tooling.tool_sdk import ToolSDK

logger = logging.getLogger(__name__)


# ── WorkflowTools ──

class WorkflowTools:
    """Adapter providing Workflow Engine tools for AI Agent.

    Exposes workflow management operations as discoverable tools:
    create, execute, monitor, and manage DAG-based workflows.

    Supports:
        - Workflow creation and configuration
        - Workflow execution (run, pause, resume, cancel)
        - Workflow status monitoring
        - Workflow history and results
        - Workflow template management

    Usage:
        wf_tools = WorkflowTools()
        tools = wf_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize workflow tools adapter."""
        self._sdk = ToolSDK()
        self._initialized: bool = False
        logger.info("WorkflowTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("WorkflowTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("WorkflowTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all workflow tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── workflow.create ──
        definitions.append(
            ToolDefinition(
                name="workflow.create",
                description="Create a new workflow definition",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "create", "dag"],
                capability="workflow",
                permission="workflow.write",
                risk_level="low",
                inputs=[
                    ToolInput(name="name", type="string", description="Workflow name", required=True),
                    ToolInput(name="description", type="string", description="Workflow description"),
                    ToolInput(name="dag_definition", type="object", description="DAG structure definition", required=True),
                    ToolInput(name="schedule", type="string", description="Cron schedule (optional)"),
                    ToolInput(name="tags", type="array", description="Workflow tags"),
                ],
                outputs=[
                    ToolOutput(name="workflow_id", type="string", description="Created workflow ID"),
                    ToolOutput(name="status", type="string", description="Creation status"),
                ],
                timeout_seconds=30.0,
                is_idempotent=False,
            )
        )

        # ── workflow.run ──
        definitions.append(
            ToolDefinition(
                name="workflow.run",
                description="Execute a workflow",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "execute", "run"],
                capability="workflow",
                permission="workflow.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="workflow_id", type="string", description="Workflow ID to run", required=True),
                    ToolInput(name="params", type="object", description="Workflow parameters"),
                    ToolInput(name="priority", type="integer", description="Execution priority", default=0),
                ],
                outputs=[
                    ToolOutput(name="execution_id", type="string", description="Execution run ID"),
                    ToolOutput(name="status", type="string", description="Execution status"),
                ],
                timeout_seconds=60.0,
                is_idempotent=False,
            )
        )

        # ── workflow.status ──
        definitions.append(
            ToolDefinition(
                name="workflow.status",
                description="Get workflow execution status",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "status", "monitor"],
                capability="workflow",
                permission="workflow.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution run ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Current status"),
                    ToolOutput(name="progress", type="number", description="Progress 0-100"),
                    ToolOutput(name="current_step", type="string", description="Current step name"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── workflow.pause ──
        definitions.append(
            ToolDefinition(
                name="workflow.pause",
                description="Pause a running workflow",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "pause"],
                capability="workflow",
                permission="workflow.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution run ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Pause result"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── workflow.resume ──
        definitions.append(
            ToolDefinition(
                name="workflow.resume",
                description="Resume a paused workflow",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "resume"],
                capability="workflow",
                permission="workflow.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution run ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Resume result"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── workflow.cancel ──
        definitions.append(
            ToolDefinition(
                name="workflow.cancel",
                description="Cancel a running workflow",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "cancel"],
                capability="workflow",
                permission="workflow.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution run ID", required=True),
                    ToolInput(name="reason", type="string", description="Cancellation reason"),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Cancel result"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── workflow.history ──
        definitions.append(
            ToolDefinition(
                name="workflow.history",
                description="Get workflow execution history",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "history"],
                capability="workflow",
                permission="workflow.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="workflow_id", type="string", description="Workflow ID"),
                    ToolInput(name="limit", type="integer", description="Max results", default=20),
                    ToolInput(name="status_filter", type="string", description="Filter by status"),
                ],
                outputs=[
                    ToolOutput(name="executions", type="array", description="Execution history"),
                    ToolOutput(name="total", type="integer", description="Total count"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── workflow.list ──
        definitions.append(
            ToolDefinition(
                name="workflow.list",
                description="List all available workflows",
                version="1.0.0",
                category="workflow",
                tags=["workflow", "list"],
                capability="workflow",
                permission="workflow.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="category", type="string", description="Filter by category"),
                    ToolInput(name="limit", type="integer", description="Max results", default=50),
                ],
                outputs=[
                    ToolOutput(name="workflows", type="array", description="Workflow list"),
                    ToolOutput(name="total", type="integer", description="Total count"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        return definitions

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get adapter status."""
        return {
            "tool_count": len(self.get_tool_definitions()),
            "initialized": self._initialized,
        }
