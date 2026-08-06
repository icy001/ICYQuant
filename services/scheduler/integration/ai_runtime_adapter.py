"""AI Runtime Adapter — bridges the Scheduler with the AI Agent Platform.

The :class:`AIRuntimeAdapter` enables scheduled AI operations:
* Scheduled inference jobs
* Periodic AI agent execution
* AI workflow orchestration
* Model training pipeline scheduling

Pipeline::

    Scheduler ──→ AIRuntimeAdapter ──→ AI Platform
                      │                    │
               Inference / Agent      Model / Tool
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AIAdapterState(enum.Enum):
    """AI adapter lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    ERROR = "error"


class AIRuntimeAdapter:
    """Adapter for AI runtime integration.

    Responsibilities:
    * Schedule periodic AI inference jobs
    * Trigger AI agent execution cycles
    * Orchestrate AI workflows (data prep → train → evaluate → deploy)
    * Monitor AI job status and metrics

    Usage::

        adapter = AIRuntimeAdapter(ai_platform=platform)
        await adapter.connect()
        await adapter.schedule_inference("price_predictor", cron="0 */1 * * *")
        await adapter.schedule_agent("market_analyst", interval="5m")
    """

    def __init__(self, ai_platform: Any = None) -> None:
        self._platform = ai_platform
        self._state = AIAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._inference_jobs: Dict[str, Dict[str, Any]] = {}
        self._agent_jobs: Dict[str, Dict[str, Any]] = {}
        self._workflow_jobs: Dict[str, Dict[str, Any]] = {}
        self._execution_count: int = 0

    @property
    def state(self) -> AIAdapterState:
        return self._state

    @property
    def total_jobs(self) -> int:
        return len(self._inference_jobs) + len(self._agent_jobs) + len(self._workflow_jobs)

    @property
    def execution_count(self) -> int:
        return self._execution_count

    async def connect(self) -> None:
        self._set_state(AIAdapterState.CONNECTING)
        try:
            if self._platform and hasattr(self._platform, "connect"):
                await self._platform.connect()
            self._set_state(AIAdapterState.CONNECTED)
            logger.info("AIRuntimeAdapter: connected")
        except Exception as exc:
            self._set_state(AIAdapterState.ERROR)
            logger.error("AIRuntimeAdapter: connection failed: %s", exc)
            raise

    async def disconnect(self) -> None:
        self._inference_jobs.clear()
        self._agent_jobs.clear()
        self._workflow_jobs.clear()
        self._set_state(AIAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "total_jobs": self.total_jobs}

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    async def schedule_inference(self, model_id: str, cron: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a periodic model inference job."""
        self._inference_jobs[model_id] = {
            "model_id": model_id, "cron": cron, "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        logger.info("AIRuntimeAdapter: scheduled inference for %s", model_id)
        return {"model_id": model_id, "status": "scheduled"}

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------

    async def schedule_agent(self, agent_id: str, interval: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule periodic AI agent execution."""
        self._agent_jobs[agent_id] = {
            "agent_id": agent_id, "interval": interval, "context": context or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        logger.info("AIRuntimeAdapter: scheduled agent %s", agent_id)
        return {"agent_id": agent_id, "status": "scheduled"}

    async def execute_agent(self, agent_id: str) -> Dict[str, Any]:
        """Trigger immediate agent execution."""
        self._execution_count += 1
        result = {"agent_id": agent_id, "status": "executing", "timestamp": datetime.now(timezone.utc).isoformat()}
        if self._platform and hasattr(self._platform, "execute_agent"):
            result["output"] = await self._platform.execute_agent(agent_id)
        return result

    # ------------------------------------------------------------------
    # AI Workflow
    # ------------------------------------------------------------------

    async def schedule_ai_workflow(self, workflow_id: str, cron: Optional[str] = None, pipeline: Optional[List[str]] = None) -> Dict[str, Any]:
        """Schedule an AI workflow (data → train → evaluate → deploy)."""
        self._workflow_jobs[workflow_id] = {
            "workflow_id": workflow_id, "cron": cron, "pipeline": pipeline or [],
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        logger.info("AIRuntimeAdapter: scheduled AI workflow %s", workflow_id)
        return {"workflow_id": workflow_id, "status": "scheduled"}

    def _set_state(self, state: AIAdapterState) -> None:
        with self._lock:
            self._state = state
