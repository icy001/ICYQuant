"""Agent Registry — unified agent registration, lookup, and lifecycle management.

Pipeline:
    AgentRegistration
        -> register() / unregister()
        -> Registry (in-memory store)
        -> lookup() / list_by_capability() / list_by_role()
        -> Discovery / Router / Scheduler

The Agent Registry is the single source of truth for all agents in the
multi-agent system. It supports dynamic registration and deregistration
at runtime, enabling plugin-based agent extension.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Runtime status of a registered agent."""
    REGISTERED = "registered"
    IDLE = "idle"
    BUSY = "busy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    SHUTDOWN = "shutdown"


class AgentRole(str, Enum):
    """Role classification for RBAC-style agent permissions."""
    COORDINATOR = "coordinator"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    STRATEGIST = "strategist"
    RISK_MANAGER = "risk_manager"
    EXECUTOR = "executor"
    REPORTER = "reporter"
    OBSERVER = "observer"


@dataclass
class AgentRegistration:
    """Registration entry for an agent in the multi-agent system.

    Attributes:
        agent_id: Unique agent identifier.
        name: Human-readable agent name.
        role: Agent role classification.
        capabilities: List of capability tags (e.g. "market.analysis").
        version: Agent version string.
        priority: Scheduling priority (higher = more important).
        metadata: Arbitrary agent metadata.
        handler: Reference to the agent instance or factory callable.
    """

    agent_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    role: AgentRole = AgentRole.OBSERVER
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Any] = field(repr=False, default=None)

    # ── Runtime state (managed by registry) ──
    status: AgentStatus = AgentStatus.REGISTERED
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: float = field(default_factory=time.monotonic)

    def __hash__(self) -> int:
        return hash(self.agent_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AgentRegistration):
            return False
        return self.agent_id == other.agent_id

    def to_dict(self) -> Dict[str, Any]:
        """Return registration as a dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "version": self.version,
            "priority": self.priority,
            "metadata": self.metadata,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
        }


class AgentRegistry:
    """Central registry for all agents in the multi-agent system.

    Maintains a unified index of all registered agents with support for
    dynamic registration, lookup, and capability-based search.

    Supports:
        - Agent registration / unregistration
        - Name-based, ID-based, and capability-based lookup
        - Role-based listing
        - Status tracking and heartbeat management
        - Priority-ordered retrieval

    Usage:
        registry = AgentRegistry()
        await registry.initialize()
        reg = AgentRegistration(name="market_agent", role=AgentRole.ANALYST, ...)
        registry.register(reg)
        agents = registry.list_by_capability("market.analysis")
    """

    def __init__(self) -> None:
        """Initialize an empty agent registry."""
        self._agents: Dict[str, AgentRegistration] = {}
        self._capability_index: Dict[str, List[str]] = {}  # capability -> [agent_id]
        self._role_index: Dict[AgentRole, List[str]] = {}
        self._initialized: bool = False
        logger.info("AgentRegistry created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the registry."""
        if self._initialized:
            logger.warning("AgentRegistry already initialized")
            return
        self._initialized = True
        logger.info("AgentRegistry initialized")

    async def shutdown(self) -> None:
        """Shut down and clear all registrations."""
        if not self._initialized:
            return
        self._agents.clear()
        self._capability_index.clear()
        self._role_index.clear()
        self._initialized = False
        logger.info("AgentRegistry shutdown complete")

    # ── Registration ──

    def register(self, agent: AgentRegistration) -> None:
        """Register an agent.

        Args:
            agent: Agent registration entry.

        Raises:
            ValueError: If an agent with the same name or ID already exists.
            RuntimeError: If the registry is not initialized.
        """
        if not self._initialized:
            raise RuntimeError("AgentRegistry not initialized")

        if agent.agent_id in self._agents:
            raise ValueError(f"Agent already registered: {agent.agent_id}")
        if agent.name and any(a.name == agent.name for a in self._agents.values()):
            raise ValueError(f"Agent name already exists: {agent.name}")

        self._agents[agent.agent_id] = agent
        self._update_indices_add(agent)
        logger.info("Agent registered: %s (role=%s, capabilities=%s)",
                     agent.name, agent.role.value, agent.capabilities)

    def unregister(self, agent_id: str) -> Optional[AgentRegistration]:
        """Unregister an agent by ID.

        Args:
            agent_id: The agent's unique identifier.

        Returns:
            The removed registration, or None if not found.
        """
        if not self._initialized:
            raise RuntimeError("AgentRegistry not initialized")

        agent = self._agents.pop(agent_id, None)
        if agent:
            self._update_indices_remove(agent)
            agent.status = AgentStatus.SHUTDOWN
            logger.info("Agent unregistered: %s", agent.name)
        return agent

    # ── Index Helpers ──

    def _update_indices_add(self, agent: AgentRegistration) -> None:
        """Update capability and role indices on registration."""
        for cap in agent.capabilities:
            self._capability_index.setdefault(cap, []).append(agent.agent_id)
        self._role_index.setdefault(agent.role, []).append(agent.agent_id)

    def _update_indices_remove(self, agent: AgentRegistration) -> None:
        """Update capability and role indices on unregistration."""
        for cap in agent.capabilities:
            if cap in self._capability_index:
                ids = self._capability_index[cap]
                if agent.agent_id in ids:
                    ids.remove(agent.agent_id)
                if not ids:
                    del self._capability_index[cap]
        if agent.role in self._role_index:
            ids = self._role_index[agent.role]
            if agent.agent_id in ids:
                ids.remove(agent.agent_id)
            if not ids:
                del self._role_index[agent.role]

    # ── Lookup ──

    def lookup(self, identifier: str) -> Optional[AgentRegistration]:
        """Look up an agent by ID or name.

        Args:
            identifier: Agent ID or name.

        Returns:
            The matching AgentRegistration, or None if not found.
        """
        if not self._initialized:
            return None

        if identifier in self._agents:
            return self._agents[identifier]
        for agent in self._agents.values():
            if agent.name == identifier:
                return agent
        return None

    def list_by_capability(self, capability: str) -> List[AgentRegistration]:
        """List all agents with a specific capability.

        Args:
            capability: Capability tag to filter by.

        Returns:
            List of matching agent registrations sorted by priority (descending).
        """
        agent_ids = self._capability_index.get(capability, [])
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]
        agents.sort(key=lambda a: a.priority, reverse=True)
        return agents

    def list_by_role(self, role: AgentRole) -> List[AgentRegistration]:
        """List all agents with a specific role.

        Args:
            role: Role to filter by.

        Returns:
            List of matching agent registrations.
        """
        agent_ids = self._role_index.get(role, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def list_all(self) -> List[AgentRegistration]:
        """List all registered agents.

        Returns:
            List of all agent registrations.
        """
        return list(self._agents.values())

    def list_active(self) -> List[AgentRegistration]:
        """List all agents that are not shut down.

        Returns:
            List of active agent registrations.
        """
        return [
            a for a in self._agents.values()
            if a.status != AgentStatus.SHUTDOWN
        ]

    # ── Status ──

    def update_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update the runtime status of an agent.

        Args:
            agent_id: Agent identifier.
            status: New status value.
        """
        agent = self._agents.get(agent_id)
        if agent:
            agent.status = status
            logger.debug("Agent %s status -> %s", agent.name, status.value)

    def heartbeat(self, agent_id: str) -> None:
        """Record a heartbeat from an agent.

        Args:
            agent_id: Agent identifier.
        """
        agent = self._agents.get(agent_id)
        if agent:
            agent.last_heartbeat = time.monotonic()

    @property
    def count(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the registry state.

        Returns:
            Dict with agent counts and status breakdown.
        """
        status_counts: Dict[str, int] = {}
        for agent in self._agents.values():
            s = agent.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "initialized": self._initialized,
            "total_agents": len(self._agents),
            "capability_count": len(self._capability_index),
            "role_count": len(self._role_index),
            "status_breakdown": status_counts,
        }
