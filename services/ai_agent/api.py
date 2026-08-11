"""
AI Agent REST API endpoints.

Provides unified HTTP interface for agent operations:
    POST /agent/run       - Execute a goal-driven agent run
    POST /agent/chat      - Chat-style interaction
    POST /agent/task      - Submit a task
    GET  /agent/session   - Get session details
    GET  /agent/memory    - Query agent memory
    GET  /agent/history   - Get execution history
    GET  /agent/status    - Service health and metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.agent_engine import AgentRequest, AgentResponse
from services.ai_agent.agent_service import AgentService

logger = logging.getLogger(__name__)


# ── API Models ──


@dataclass
class RunRequest:
    """Request for POST /agent/run."""

    goal: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[float] = None


@dataclass
class ChatRequest:
    """Request for POST /agent/chat."""

    message: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRequest:
    """Request for POST /agent/task."""

    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    session_id: Optional[str] = None


@dataclass
class AgentAPIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    request_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Agent API ──


class AgentAPI:
    """REST API interface for the AI Agent Platform.

    Exposes agent capabilities through a clean HTTP-like interface
    that integrates with the ICYQuant API framework.

    Usage:
        api = AgentAPI(service)
        response = await api.run(RunRequest(goal="Analyze BTC/USDT"))
        result = await api.get_session(session_id)
    """

    def __init__(self, service: AgentService) -> None:
        self.service = service
        self._request_count: int = 0
        logger.info("AgentAPI initialized")

    # ── Endpoints ──

    async def run(self, request: RunRequest) -> AgentAPIResponse:
        """Execute a goal-driven agent run.

        POST /agent/run

        Args:
            request: Run request with goal and context.

        Returns:
            API response with execution result.
        """
        self._request_count += 1
        try:
            response = await self.service.run(
                goal=request.goal,
                context=request.context,
                constraints=request.constraints,
                session_id=request.session_id,
                metadata=request.metadata,
                timeout_seconds=request.timeout_seconds,
            )
            return AgentAPIResponse(
                success=response.status.value == "completed",
                data={
                    "session_id": response.session_id,
                    "plan": response.plan.to_summary() if response.plan else None,
                    "reasoning": response.reasoning.to_summary() if response.reasoning else None,
                    "result": response.result,
                    "execution_time_seconds": response.execution_time_seconds,
                },
                request_id=response.request_id,
            )
        except Exception as e:
            logger.exception("Agent run failed")
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def chat(self, request: ChatRequest) -> AgentAPIResponse:
        """Chat-style interaction with the agent.

        POST /agent/chat

        Args:
            request: Chat request with message and session.

        Returns:
            API response with agent reply.
        """
        self._request_count += 1
        try:
            response = await self.service.chat(
                message=request.message,
                session_id=request.session_id,
            )
            return AgentAPIResponse(
                success=response.status.value == "completed",
                data={
                    "session_id": response.session_id,
                    "response": response.result,
                    "reasoning": response.reasoning.to_summary() if response.reasoning else None,
                },
                request_id=response.request_id,
            )
        except Exception as e:
            logger.exception("Chat failed")
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def submit_task(self, request: TaskRequest) -> AgentAPIResponse:
        """Submit a task for execution.

        POST /agent/task

        Args:
            request: Task submission request.

        Returns:
            API response with task ID.
        """
        self._request_count += 1
        task_id = uuid4().hex
        try:
            # Use run endpoint with task context
            response = await self.service.run(
                goal=f"Execute task: {request.task_type}",
                context={"payload": request.payload},
                session_id=request.session_id,
            )
            return AgentAPIResponse(
                success=True,
                data={
                    "task_id": task_id,
                    "session_id": response.session_id,
                    "status": "submitted",
                },
                request_id=response.request_id,
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def get_session(self, session_id: str) -> AgentAPIResponse:
        """Get session details.

        GET /agent/session/{session_id}

        Args:
            session_id: Session identifier.

        Returns:
            API response with session data.
        """
        try:
            session = await self.service.get_session(session_id)
            if not session:
                return AgentAPIResponse(
                    success=False,
                    error=f"Session not found: {session_id}",
                )
            return AgentAPIResponse(
                success=True,
                data=session,
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def list_sessions(self) -> AgentAPIResponse:
        """List all active sessions.

        GET /agent/session

        Returns:
            API response with session list.
        """
        try:
            sessions = await self.service.list_sessions()
            return AgentAPIResponse(
                success=True,
                data={"sessions": sessions, "count": len(sessions)},
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def get_memory(self, key: Optional[str] = None) -> AgentAPIResponse:
        """Query agent memory.

        GET /agent/memory?key={key}

        Args:
            key: Optional specific memory key to retrieve.

        Returns:
            API response with memory data.
        """
        try:
            # Delegate to memory manager through the service
            summary = self.service.get_status()
            memory_summary = summary.get("memory", {})
            return AgentAPIResponse(
                success=True,
                data={"memory_summary": memory_summary},
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def get_history(self, session_id: Optional[str] = None) -> AgentAPIResponse:
        """Get execution history.

        GET /agent/history?session_id={session_id}

        Args:
            session_id: Optional session filter.

        Returns:
            API response with execution history.
        """
        try:
            if session_id:
                sessions = [await self.service.get_session(session_id)]
            else:
                sessions = await self.service.list_sessions()

            return AgentAPIResponse(
                success=True,
                data={
                    "history": sessions,
                    "count": len(sessions),
                },
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    async def get_status(self) -> AgentAPIResponse:
        """Get service health and status.

        GET /agent/status

        Returns:
            API response with status info.
        """
        try:
            status = self.service.get_status()
            return AgentAPIResponse(
                success=True,
                data=status,
            )
        except Exception as e:
            return AgentAPIResponse(
                success=False,
                error=str(e),
            )

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get API summary."""
        return {
            "total_requests": self._request_count,
            "service_state": self.service.state.value,
        }
