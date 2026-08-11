"""
AI Agent Service - Main orchestrator.

The top-level service facade that wires together all AI Agent Platform
components and provides a unified entry point for the rest of ICYQuant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.agent_engine import AgentEngine, AgentRequest, AgentResponse
from services.ai_agent.agent_factory import AgentBuildContext, AgentFactory
from services.ai_agent.agent_manager import AgentManager
from services.ai_agent.agent_registry import AgentDescriptor, AgentRegistry
from services.ai_agent.agent_repository import AgentRepository
from services.ai_agent.agent_runtime import AgentRuntime, RuntimeConfig
from services.ai_agent.planner import Planner
from services.ai_agent.reasoning_engine import ReasoningEngine
from services.ai_agent.session_manager import SessionManager
from services.ai_agent.task_scheduler import TaskScheduler
from services.ai_agent.workflow_executor import WorkflowExecutor

logger = logging.getLogger(__name__)


# ── Service State ──


class ServiceState(str, Enum):
    """AI Agent Service lifecycle states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class AgentServiceConfig:
    """Configuration for the AI Agent Service."""

    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    enable_scheduler: bool = True
    enable_persistence: bool = True
    enable_metrics: bool = True
    enable_telemetry: bool = True
    enable_api: bool = True
    max_sessions: int = 1000
    default_timeout_seconds: float = 300.0


# ── Agent Service ──


class AgentService:
    """Unified AI Agent Service orchestrator.

    Wires together all platform components and exposes a clean
    high-level interface for the rest of the ICYQuant platform.

    Usage:
        service = AgentService()
        await service.start()
        response = await service.run(request)
        await service.stop()
    """

    def __init__(self, config: Optional[AgentServiceConfig] = None) -> None:
        self.config = config or AgentServiceConfig()
        self.state: ServiceState = ServiceState.CREATED

        # ── Component Initialization ──
        self.registry = AgentRegistry()
        self.repository = AgentRepository()
        self.runtime = AgentRuntime(config=self.config.runtime)
        self.factory = AgentFactory(registry=self.registry, repository=self.repository)
        self.manager = AgentManager(
            factory=self.factory,
            registry=self.registry,
            repository=self.repository,
        )
        self.planner = Planner()
        self.reasoner = ReasoningEngine()
        self.workflow_executor = WorkflowExecutor()
        self.session_manager = SessionManager(max_sessions=self.config.max_sessions)
        self.task_scheduler: Optional[TaskScheduler] = None
        if self.config.enable_scheduler:
            self.task_scheduler = TaskScheduler()

        # ── Engine ──
        self.engine = AgentEngine(
            runtime=self.runtime,
            planner=self.planner,
            reasoner=self.reasoner,
            workflow_executor=self.workflow_executor,
            session_manager=self.session_manager,
            task_scheduler=self.task_scheduler,
        )

        logger.info("AgentService created")

    # ── Lifecycle ──

    async def start(self) -> None:
        """Start the AI Agent Service and all subsystems."""
        self.state = ServiceState.INITIALIZING
        logger.info("AgentService starting...")

        try:
            await self.manager.initialize()
            await self.engine.initialize()
            self.state = ServiceState.RUNNING
            logger.info("AgentService started successfully")
        except Exception as e:
            self.state = ServiceState.DEGRADED
            logger.error(f"AgentService start failed: {e}")
            raise

    async def stop(self) -> None:
        """Gracefully stop the AI Agent Service."""
        self.state = ServiceState.STOPPING
        logger.info("AgentService stopping...")

        try:
            await self.engine.shutdown()
            await self.manager.shutdown()
        finally:
            self.state = ServiceState.STOPPED
            logger.info("AgentService stopped")

    # ── Core Operations ──

    async def run(self, goal: str, **kwargs: Any) -> AgentResponse:
        """Execute a goal-driven agent run.

        This is the primary high-level API for the ICYQuant platform.

        Args:
            goal: Natural language description of what to accomplish.
            **kwargs: Additional context, constraints, and metadata.

        Returns:
            AgentResponse with plan, reasoning, and execution result.
        """
        if self.state != ServiceState.RUNNING:
            raise RuntimeError(f"AgentService not running. Current state: {self.state.value}")

        request = AgentRequest(
            goal=goal,
            context=kwargs.get("context", {}),
            constraints=kwargs.get("constraints", {}),
            metadata=kwargs.get("metadata", {}),
            session_id=kwargs.get("session_id"),
            timeout_seconds=kwargs.get("timeout_seconds", self.config.default_timeout_seconds),
        )
        return await self.engine.execute(request)

    async def chat(self, message: str, session_id: Optional[str] = None) -> AgentResponse:
        """Chat-style interaction with the agent.

        Args:
            message: User message text.
            session_id: Optional existing session to continue.

        Returns:
            AgentResponse from the agent.
        """
        if self.state != ServiceState.RUNNING:
            raise RuntimeError(f"AgentService not running. Current state: {self.state.value}")

        request = AgentRequest(
            goal=message,
            session_id=session_id,
        )
        return await self.engine.execute(request)

    async def plan(self, goal: str, **kwargs: Any) -> Any:
        """Run only the planning phase and return plan.

        Args:
            goal: Description of what to plan.
            **kwargs: Additional context.

        Returns:
            Plan object with decomposed tasks.
        """
        if self.state != ServiceState.RUNNING:
            raise RuntimeError(f"AgentService not running. Current state: {self.state.value}")

        request = AgentRequest(
            goal=goal,
            context=kwargs.get("context", {}),
            constraints=kwargs.get("constraints", {}),
            session_id=kwargs.get("session_id"),
        )
        return await self.engine.plan_only(request)

    # ── Agent Management ──

    def create_agent(self, agent_type: str, name: str, **config: Any) -> Dict[str, Any]:
        """Create a new managed agent instance.

        Args:
            agent_type: Type of agent from registry.
            name: Display name for the agent.
            **config: Agent-specific configuration.

        Returns:
            Agent summary with agent_id and type.
        """
        ctx = AgentBuildContext(
            agent_type=agent_type,
            name=name,
            config=config,
        )
        return self.manager.create_agent(ctx)

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all managed agents."""
        return self.manager.list_agents()

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent's information."""
        return self.manager.get_agent(agent_id)

    async def terminate_agent(self, agent_id: str) -> bool:
        """Terminate a managed agent."""
        return await self.manager.terminate_agent(agent_id)

    # ── Session Management ──

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details."""
        session = await self.session_manager.get_session(session_id)
        if session:
            return session.to_dict()
        return None

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return await self.session_manager.list_sessions()

    # ── Registration ──

    def register_agent_type(
        self,
        descriptor: AgentDescriptor,
        agent_class: Optional[Any] = None,
    ) -> None:
        """Register a new agent type in the registry."""
        self.registry.register(descriptor, agent_class)

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive service status."""
        return {
            "state": self.state.value,
            "engine": self.engine.get_status(),
            "manager": self.manager.get_summary(),
            "registry": self.registry.get_summary(),
            "repository": self.repository.get_summary(),
            "sessions": self.session_manager.get_summary(),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get concise service summary."""
        return {
            "state": self.state.value,
            "config": {
                "max_concurrent_agents": self.config.runtime.max_concurrent_agents,
                "max_sessions": self.config.max_sessions,
                "enable_scheduler": self.config.enable_scheduler,
            },
            "engine_summary": self.engine.get_summary(),
            "agent_count": len(self.manager.list_agents()),
        }
