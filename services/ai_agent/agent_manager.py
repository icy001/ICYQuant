"""
Agent lifecycle manager.

Manages agent instances - creation, activation, suspension, termination,
and supervision across the agent platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.exceptions import ICYQuantError

from services.ai_agent.agent_factory import AgentBuildContext, AgentFactory
from services.ai_agent.agent_registry import AgentDescriptor, AgentRegistry
from services.ai_agent.agent_repository import AgentRecord, AgentRepository, AgentStatus

logger = logging.getLogger(__name__)


# ── Manager Types ──


class AgentLifecycleAction(str, Enum):
    """Actions in agent lifecycle."""

    CREATE = "create"
    ACTIVATE = "activate"
    SUSPEND = "suspend"
    RESUME = "resume"
    TERMINATE = "terminate"
    RECONFIGURE = "reconfigure"


@dataclass
class AgentLifecycleEvent:
    """Record of an agent lifecycle action."""

    agent_id: str
    action: AgentLifecycleAction
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ── Agent Manager ──


class AgentManager:
    """Central manager for agent lifecycle and supervision.

    Coordinates creation, activation, monitoring, and cleanup
    of all agent instances in the platform.

    Usage:
        manager = AgentManager(factory, registry, repository)
        agent = await manager.create_agent(ctx)
        await manager.activate_agent(agent.agent_id)
        await manager.terminate_agent(agent.agent_id)
    """

    def __init__(
        self,
        factory: AgentFactory,
        registry: AgentRegistry,
        repository: AgentRepository,
    ) -> None:
        self.factory = factory
        self.registry = registry
        self.repository = repository
        self.active_agents: Dict[str, Any] = {}  # agent_id -> agent instance
        self.lifecycle_history: List[AgentLifecycleEvent] = []
        self._initialized: bool = False
        logger.info("AgentManager created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the agent manager."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("AgentManager initialized")

    async def shutdown(self) -> None:
        """Gracefully shut down all managed agents."""
        logger.info(f"AgentManager shutting down {len(self.active_agents)} agents")
        agent_ids = list(self.active_agents.keys())
        for agent_id in agent_ids:
            try:
                await self.terminate_agent(agent_id)
            except Exception:
                logger.exception(f"Error terminating agent {agent_id} during shutdown")

        self.active_agents.clear()
        self._initialized = False
        logger.info("AgentManager shut down complete")

    # ── Agent Operations ──

    def create_agent(self, ctx: AgentBuildContext) -> Dict[str, Any]:
        """Create a new agent instance via the factory.

        Args:
            ctx: Build context specifying type, name, and configuration.

        Returns:
            Agent summary dict with agent_id and type.
        """
        agent = self.factory.create(ctx)
        agent_id = getattr(agent, "agent_id", uuid4().hex)
        self.active_agents[agent_id] = agent
        self.repository.update_status(agent_id, AgentStatus.IDLE)
        self._record_lifecycle(agent_id, AgentLifecycleAction.CREATE)

        logger.info(f"Agent created: {agent_id} [{ctx.agent_type}]")
        return {
            "agent_id": agent_id,
            "agent_type": ctx.agent_type,
            "name": ctx.name,
            "status": AgentStatus.IDLE.value,
        }

    async def activate_agent(self, agent_id: str) -> bool:
        """Activate an agent for execution.

        Transitions agent from IDLE to ACTIVE state.
        """
        record = self.repository.get(agent_id)
        if not record:
            raise ICYQuantError(f"Agent not found: {agent_id}")

        if record.status != AgentStatus.IDLE:
            logger.warning(f"Agent [{agent_id}] not idle, current: {record.status.value}")
            return False

        self.repository.update_status(agent_id, AgentStatus.ACTIVE)
        self._record_lifecycle(agent_id, AgentLifecycleAction.ACTIVATE)
        logger.info(f"Agent activated: {agent_id}")
        return True

    async def suspend_agent(self, agent_id: str) -> bool:
        """Suspend an active agent."""
        record = self.repository.get(agent_id)
        if not record:
            raise ICYQuantError(f"Agent not found: {agent_id}")

        self.repository.update_status(agent_id, AgentStatus.IDLE)
        self._record_lifecycle(agent_id, AgentLifecycleAction.SUSPEND)
        logger.info(f"Agent suspended: {agent_id}")
        return True

    async def resume_agent(self, agent_id: str) -> bool:
        """Resume a suspended agent."""
        record = self.repository.get(agent_id)
        if not record:
            raise ICYQuantError(f"Agent not found: {agent_id}")

        self.repository.update_status(agent_id, AgentStatus.ACTIVE)
        self._record_lifecycle(agent_id, AgentLifecycleAction.RESUME)
        logger.info(f"Agent resumed: {agent_id}")
        return True

    async def terminate_agent(self, agent_id: str) -> bool:
        """Terminate an agent and clean up resources."""
        record = self.repository.get(agent_id)
        if not record:
            logger.warning(f"Agent not found for termination: {agent_id}")
            return False

        # Call agent shutdown if available
        agent = self.active_agents.pop(agent_id, None)
        if agent and hasattr(agent, "shutdown"):
            try:
                await agent.shutdown()
            except Exception:
                logger.exception(f"Error during agent [{agent_id}] shutdown")

        self.repository.update_status(agent_id, AgentStatus.STOPPED)
        self._record_lifecycle(agent_id, AgentLifecycleAction.TERMINATE)
        logger.info(f"Agent terminated: {agent_id}")
        return True

    # ── Queries ──

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent instance and record info."""
        record = self.repository.get(agent_id)
        if not record:
            return None
        agent = self.active_agents.get(agent_id)
        return {
            "record": record.to_dict(),
            "is_active": agent is not None,
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents with status."""
        return [r.to_dict() for r in self.repository.get_all()]

    def count_by_status(self) -> Dict[str, int]:
        """Count agents grouped by status."""
        counts: Dict[str, int] = {}
        for record in self.repository.get_all():
            counts[record.status.value] = counts.get(record.status.value, 0) + 1
        return counts

    # ── Lifecycle History ──

    def _record_lifecycle(self, agent_id: str, action: AgentLifecycleAction) -> None:
        """Record a lifecycle event."""
        event = AgentLifecycleEvent(agent_id=agent_id, action=action)
        self.lifecycle_history.append(event)

    def get_lifecycle_history(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get lifecycle event history, optionally filtered by agent."""
        events = self.lifecycle_history
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]
        return [
            {
                "agent_id": e.agent_id,
                "action": e.action.value,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]

    # ── Summary ──

    def get_summary(self) -> Dict[str, Any]:
        """Get agent manager summary."""
        return {
            "active_agent_count": len(self.active_agents),
            "total_managed": len(self.repository.get_all()),
            "by_status": self.count_by_status(),
            "lifecycle_events": len(self.lifecycle_history),
            "repository_summary": self.repository.get_summary(),
        }
