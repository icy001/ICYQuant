"""
Unified AI Agent Engine.

Central execution pipeline orchestrating the full agent lifecycle:
    User Request → Planning → Reasoning → Execution → Response

Acts as the primary intelligent decision-making entry point for ICYQuant.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from shared.exceptions import ICYQuantError

from services.ai_agent.agent_context import AgentContext, ExecutionContext
from services.ai_agent.agent_manager import AgentManager
from services.ai_agent.agent_registry import AgentRegistry
from services.ai_agent.agent_repository import AgentRepository
from services.ai_agent.agent_runtime import AgentRuntime, RuntimeConfig
from services.ai_agent.planner import Plan, Planner
from services.ai_agent.reasoning_engine import ReasoningEngine, ReasoningResult
from services.ai_agent.session_manager import Session, SessionManager
from services.ai_agent.task_scheduler import TaskScheduler
from services.ai_agent.workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


# ── Engine Types ──


class ExecutionStatus(str, Enum):
    """Agent execution status."""

    PENDING = "pending"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRequest:
    """Incoming request to the agent engine."""

    request_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: Optional[str] = None
    goal: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_seconds: Optional[float] = None


@dataclass
class AgentResponse:
    """Response from agent execution."""

    request_id: str
    session_id: str
    status: ExecutionStatus
    plan: Optional[Plan] = None
    reasoning: Optional[ReasoningResult] = None
    result: Any = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Engine Pipeline ──


class AgentEngine:
    """Unified AI Agent Engine.

    Orchestrates the complete agent execution pipeline:
        1. Session management
        2. Planning (goal → plan)
        3. Reasoning (plan → decision)
        4. Execution (decision → result)
        5. Memory persistence
        6. Response assembly

    Usage:
        engine = AgentEngine(runtime, planner, reasoner, ...)
        await engine.initialize()
        response = await engine.execute(AgentRequest(goal="Analyze market data"))
        await engine.shutdown()
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        planner: Planner,
        reasoner: ReasoningEngine,
        workflow_executor: WorkflowExecutor,
        session_manager: SessionManager,
        task_scheduler: Optional[TaskScheduler] = None,
    ) -> None:
        self.runtime = runtime
        self.planner = planner
        self.reasoner = reasoner
        self.workflow_executor = workflow_executor
        self.session_manager = session_manager
        self.task_scheduler = task_scheduler
        self._initialized: bool = False
        self._stats: Dict[str, int] = {
            "total_requests": 0,
            "completed": 0,
            "failed": 0,
        }
        logger.info("AgentEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the engine and all subsystems."""
        if self._initialized:
            return

        logger.info("AgentEngine initializing...")
        await self.runtime.initialize()
        self._initialized = True
        logger.info("AgentEngine initialized")

    async def shutdown(self) -> None:
        """Gracefully shut down the engine."""
        logger.info("AgentEngine shutting down...")
        await self.runtime.shutdown()
        self._initialized = False
        logger.info("AgentEngine shut down", extra={"stats": self._stats})

    # ── Execution Pipeline ──

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Execute the full agent pipeline for a request.

        Args:
            request: Agent request with goal and context.

        Returns:
            AgentResponse with plan, reasoning, and result.
        """
        if not self._initialized:
            raise ICYQuantError("AgentEngine not initialized. Call initialize() first.")

        start_time = time.monotonic()
        self._stats["total_requests"] += 1

        # Ensure session exists
        session = await self._ensure_session(request)

        logger.info(
            f"AgentEngine executing request [{request.request_id}]",
            extra={"goal": request.goal[:100], "session_id": session.session_id},
        )

        try:
            # ── Phase 1: Planning ──
            plan = await self._plan_phase(request, session)

            # ── Phase 2: Reasoning ──
            reasoning = await self._reasoning_phase(request, plan, session)

            # ── Phase 3: Execution ──
            result = await self._execution_phase(request, plan, reasoning, session)

            # ── Phase 4: Response ──
            self._stats["completed"] += 1
            elapsed = time.monotonic() - start_time

            response = AgentResponse(
                request_id=request.request_id,
                session_id=session.session_id,
                status=ExecutionStatus.COMPLETED,
                plan=plan,
                reasoning=reasoning,
                result=result,
                execution_time_seconds=elapsed,
            )

            logger.info(
                f"AgentEngine completed request [{request.request_id}] in {elapsed:.2f}s",
            )
            return response

        except Exception as e:
            self._stats["failed"] += 1
            elapsed = time.monotonic() - start_time
            logger.exception(
                f"AgentEngine failed request [{request.request_id}]: {e}",
            )
            return AgentResponse(
                request_id=request.request_id,
                session_id=session.session_id if session else "",
                status=ExecutionStatus.FAILED,
                errors=[{"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}],
                execution_time_seconds=elapsed,
            )

    # ── Pipeline Phases ──

    async def _ensure_session(self, request: AgentRequest) -> Session:
        """Get or create a session for the request."""
        if request.session_id:
            session = await self.session_manager.get_session(request.session_id)
            if session:
                return session

        return await self.session_manager.create_session(
            metadata=request.metadata,
        )

    async def _plan_phase(self, request: AgentRequest, session: Session) -> Plan:
        """Planning phase: decompose goal into execution plan."""
        logger.debug(f"Planning phase for request [{request.request_id}]")
        plan = self.planner.plan(
            goal=request.goal,
            context=request.context,
            constraints=request.constraints,
            session_id=session.session_id,
        )
        return plan

    async def _reasoning_phase(
        self,
        request: AgentRequest,
        plan: Plan,
        session: Session,
    ) -> ReasoningResult:
        """Reasoning phase: analyze plan and make decisions."""
        logger.debug(f"Reasoning phase for request [{request.request_id}]")
        reasoning = self.reasoner.reason(
            plan=plan,
            context=request.context,
            session_id=session.session_id,
        )
        return reasoning

    async def _execution_phase(
        self,
        request: AgentRequest,
        plan: Plan,
        reasoning: ReasoningResult,
        session: Session,
    ) -> Any:
        """Execution phase: run the workflow."""
        logger.debug(f"Execution phase for request [{request.request_id}]")
        result = await self.workflow_executor.execute(
            plan=plan,
            reasoning=reasoning,
            session_id=session.session_id,
        )
        return result

    # ── Direct Execution (without pipeline) ──

    async def plan_only(self, request: AgentRequest) -> Plan:
        """Run only the planning phase."""
        session = await self._ensure_session(request)
        return self.planner.plan(
            goal=request.goal,
            context=request.context,
            constraints=request.constraints,
            session_id=session.session_id,
        )

    async def reason_only(self, request: AgentRequest, plan: Plan) -> ReasoningResult:
        """Run only the reasoning phase."""
        session = await self._ensure_session(request)
        return self.reasoner.reason(
            plan=plan,
            context=request.context,
            session_id=session.session_id,
        )

    # ── Diagnostics ──

    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        return {
            "initialized": self._initialized,
            "stats": dict(self._stats),
            "runtime": self.runtime.get_status() if self._initialized else None,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get engine summary."""
        return {
            "initialized": self._initialized,
            "total_requests": self._stats["total_requests"],
            "completed": self._stats["completed"],
            "failed": self._stats["failed"],
            "success_rate": (
                self._stats["completed"] / max(self._stats["total_requests"], 1)
            ),
        }
