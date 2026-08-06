"""Scheduler SDK — client SDK for interacting with the Distributed Scheduler.

The :class:`SchedulerSDK` provides a clean Python API for:
* Scheduling jobs and workflows
* Managing schedules (create, update, delete, pause)
* Querying scheduler state
* Monitoring execution progress

Supports multiple transport backends:
* Direct (in-process)
* REST (HTTP)
* gRPC (reserved)

Usage::

    from services.scheduler.integration.sdk import SchedulerSDK

    sdk = SchedulerSDK()
    await sdk.connect()

    # Schedule a workflow
    await sdk.schedule(
        workflow="daily_research",
        trigger="0 0 8 * * MON-FRI",
    )

    # Schedule a strategy
    await sdk.schedule_strategy(
        strategy_id="momentum_v1",
        cron="0 */5 * * *",
    )

    # List running jobs
    jobs = await sdk.list_jobs(status="running")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SDKClient:
    """Transport client for the SDK."""

    def __init__(self, base_url: str = "http://localhost:8080") -> None:
        self.base_url = base_url
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request. Stub — in production uses httpx/aiohttp."""
        return {"status": "ok"}


class SchedulerSDK:
    """Python SDK for the Distributed Scheduler.

    Provides a clean, typed API for scheduling operations.
    Supports direct (in-process), REST, and gRPC transports.

    Usage::

        sdk = SchedulerSDK(mode="direct", scheduler_engine=engine)
        await sdk.connect()
        result = await sdk.schedule(workflow="my_workflow", trigger="0 9 * * 1-5")
    """

    def __init__(
        self,
        mode: str = "rest",
        scheduler_engine: Any = None,
        base_url: str = "http://localhost:8080",
    ) -> None:
        self._mode = mode
        self._engine = scheduler_engine
        self._client = SDKClient(base_url=base_url)
        self._connected = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the scheduler."""
        if self._mode == "rest":
            await self._client.connect()
        self._connected = True
        logger.info("SchedulerSDK: connected in %s mode", self._mode)

    async def disconnect(self) -> None:
        """Disconnect from the scheduler."""
        if self._mode == "rest":
            await self._client.disconnect()
        self._connected = False
        logger.info("SchedulerSDK: disconnected")

    # ------------------------------------------------------------------
    # Schedule API
    # ------------------------------------------------------------------

    async def schedule(
        self,
        workflow: str,
        trigger: str,
        parameters: Optional[Dict[str, Any]] = None,
        schedule_id: Optional[str] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Schedule a workflow to run on a trigger.

        Args:
            workflow: Workflow name/ID to execute
            trigger: Trigger expression (cron, interval, etc.)
            parameters: Workflow parameters
            schedule_id: Optional schedule ID (auto-generated if not provided)
            description: Human-readable description

        Returns:
            Schedule creation result with schedule_id

        Example::

            await sdk.schedule(
                workflow="daily_research",
                trigger="0 0 8 * * MON-FRI",
                parameters={"universe": "CSI300"},
            )
        """
        payload = {
            "workflow": workflow,
            "trigger": trigger,
            "parameters": parameters or {},
            "schedule_id": schedule_id,
            "description": description,
        }
        logger.info("SchedulerSDK: scheduling workflow '%s' with trigger '%s'", workflow, trigger)
        return await self._call("POST", "/scheduler/schedules", payload)

    async def schedule_strategy(
        self,
        strategy_id: str,
        cron: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Schedule a trading strategy.

        Example::

            await sdk.schedule_strategy(
                strategy_id="momentum_v1",
                cron="0 */5 * * *",
            )
        """
        return await self.schedule(
            workflow=f"strategy:{strategy_id}",
            trigger=cron,
            parameters=parameters,
        )

    async def schedule_research(
        self,
        research_id: str,
        cron: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Schedule a research pipeline.

        Example::

            await sdk.schedule_research(
                research_id="factor_computation",
                cron="0 6 * * 1-5",
            )
        """
        return await self.schedule(
            workflow=f"research:{research_id}",
            trigger=cron,
            parameters=parameters,
        )

    async def schedule_ai(
        self,
        agent_id: str,
        interval: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Schedule an AI agent.

        Example::

            await sdk.schedule_ai(
                agent_id="market_analyst",
                interval="5m",
            )
        """
        return await self.schedule(
            workflow=f"ai:{agent_id}",
            trigger=f"interval:{interval}",
            parameters=context,
        )

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    async def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """List scheduled jobs."""
        return await self._call("GET", f"/scheduler/jobs?status={status or ''}&limit={limit}")

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get a specific job."""
        return await self._call("GET", f"/scheduler/jobs/{job_id}")

    async def list_schedules(self) -> Dict[str, Any]:
        """List all schedules."""
        return await self._call("GET", "/scheduler/schedules")

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status."""
        return await self._call("GET", "/scheduler/cluster")

    async def get_metrics(self) -> Dict[str, Any]:
        """Get scheduler metrics."""
        return await self._call("GET", "/scheduler/metrics")

    # ------------------------------------------------------------------
    # Management API
    # ------------------------------------------------------------------

    async def trigger_job(self, job_id: str) -> Dict[str, Any]:
        """Manually trigger a job."""
        return await self._call("POST", f"/scheduler/jobs/{job_id}/trigger")

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        return await self._call("POST", f"/scheduler/jobs/{job_id}/cancel")

    async def pause_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Pause a schedule."""
        return await self._call("POST", f"/scheduler/schedules/{schedule_id}/pause")

    async def resume_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Resume a paused schedule."""
        return await self._call("POST", f"/scheduler/schedules/{schedule_id}/resume")

    async def delete_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Delete a schedule."""
        return await self._call("DELETE", f"/scheduler/schedules/{schedule_id}")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an API call through the configured transport."""
        if self._mode == "direct" and self._engine:
            # Direct in-process call — stub
            return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
        elif self._mode == "rest":
            return await self._client.request(method, path, body)
        return {"status": "error", "error": "unsupported_mode"}
