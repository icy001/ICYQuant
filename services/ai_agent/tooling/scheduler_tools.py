"""Scheduler Tools — platform adapter for Distributed Scheduler operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Distributed Scheduler for task scheduling, cron jobs,
and batch processing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── SchedulerTools ──

class SchedulerTools:
    """Adapter providing Scheduler tools for AI Agent.

    Exposes scheduling operations as discoverable tools for the
    agent to create, manage, and monitor scheduled tasks.

    Supports:
        - Job scheduling (one-time and recurring)
        - Cron expression management
        - Job status monitoring
        - Job history
        - Job dependency management

    Usage:
        sched_tools = SchedulerTools()
        tools = sched_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize scheduler tools adapter."""
        self._initialized: bool = False
        logger.info("SchedulerTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("SchedulerTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("SchedulerTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all scheduler tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── scheduler.create_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.create_job",
                description="Create a scheduled job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "create"],
                capability="scheduler",
                permission="scheduler.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="name", type="string", description="Job name", required=True),
                    ToolInput(name="schedule", type="string", description="Cron expression or interval", required=True),
                    ToolInput(name="task_type", type="string", description="Type of task to run", required=True),
                    ToolInput(name="task_params", type="object", description="Task parameters"),
                    ToolInput(name="priority", type="integer", description="Job priority", default=0),
                    ToolInput(name="timezone", type="string", description="Timezone", default="Asia/Shanghai"),
                    ToolInput(name="enabled", type="boolean", description="Enable on creation", default=True),
                ],
                outputs=[
                    ToolOutput(name="job_id", type="string", description="Created job ID"),
                    ToolOutput(name="status", type="string", description="Creation status"),
                ],
                timeout_seconds=15.0,
                is_idempotent=False,
            )
        )

        # ── scheduler.list_jobs ──
        definitions.append(
            ToolDefinition(
                name="scheduler.list_jobs",
                description="List all scheduled jobs",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "list"],
                capability="scheduler",
                permission="scheduler.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="status", type="string", description="Filter by status"),
                    ToolInput(name="limit", type="integer", description="Max results", default=50),
                ],
                outputs=[
                    ToolOutput(name="jobs", type="array", description="Job list"),
                    ToolOutput(name="total", type="integer", description="Total count"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.get_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.get_job",
                description="Get details of a scheduled job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "detail"],
                capability="scheduler",
                permission="scheduler.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="job", type="object", description="Job details"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.pause_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.pause_job",
                description="Pause a scheduled job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "pause"],
                capability="scheduler",
                permission="scheduler.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Pause result"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.resume_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.resume_job",
                description="Resume a paused job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "resume"],
                capability="scheduler",
                permission="scheduler.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Resume result"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.delete_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.delete_job",
                description="Delete a scheduled job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "delete"],
                capability="scheduler",
                permission="scheduler.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Deletion result"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.job_history ──
        definitions.append(
            ToolDefinition(
                name="scheduler.job_history",
                description="Get execution history for a job",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "history"],
                capability="scheduler",
                permission="scheduler.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                    ToolInput(name="limit", type="integer", description="Max results", default=20),
                ],
                outputs=[
                    ToolOutput(name="runs", type="array", description="Execution history"),
                    ToolOutput(name="total", type="integer", description="Total runs"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── scheduler.trigger_job ──
        definitions.append(
            ToolDefinition(
                name="scheduler.trigger_job",
                description="Manually trigger a job execution",
                version="1.0.0",
                category="scheduler",
                tags=["scheduler", "job", "trigger"],
                capability="scheduler",
                permission="scheduler.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="job_id", type="string", description="Job ID", required=True),
                    ToolInput(name="params", type="object", description="Override parameters"),
                ],
                outputs=[
                    ToolOutput(name="execution_id", type="string", description="Execution ID"),
                    ToolOutput(name="status", type="string", description="Trigger result"),
                ],
                timeout_seconds=15.0,
                is_idempotent=False,
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
