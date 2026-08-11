"""
ICYQuant Agent Registry — centralized agent discovery and registration.

Provides agent identity, capability discovery, and lifecycle registration
for the multi-agent quant collaboration system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    REGISTERED = "registered"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class AgentInfo:
    """Registration info for an agent."""
    agent_id: str
    name: str
    agent_type: str
    status: AgentStatus = AgentStatus.REGISTERED
    capabilities: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """Centralized agent registration and discovery.

    Responsibilities:
        - Register agents with type, capabilities, status
        - Lookup agents by ID, type, or capability
        - Track agent status and lifecycle
        - Provide capability-based agent discovery
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._type_index: dict[str, list[str]] = {}
        self._capability_index: dict[str, set[str]] = {}

    def register(self, agent_id: str, name: str, agent_type: str,
                 capabilities: Optional[list[str]] = None,
                 metadata: Optional[dict[str, Any]] = None) -> AgentInfo:
        """Register an agent in the registry."""
        info = AgentInfo(
            agent_id=agent_id,
            name=name,
            agent_type=agent_type,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        self._agents[agent_id] = info

        # Index by type
        if agent_type not in self._type_index:
            self._type_index[agent_type] = []
        self._type_index[agent_type].append(agent_id)

        # Index by capability
        for cap in info.capabilities:
            if cap not in self._capability_index:
                self._capability_index[cap] = set()
            self._capability_index[cap].add(agent_id)

        logger.info("Registered agent %s [%s]", agent_id, agent_type)
        return info

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        info = self._agents.pop(agent_id, None)
        if info is None:
            return False
        self._type_index[info.agent_type] = [
            aid for aid in self._type_index.get(info.agent_type, []) if aid != agent_id
        ]
        for cap in info.capabilities:
            if cap in self._capability_index:
                self._capability_index[cap].discard(agent_id)
        return True

    def get(self, agent_id: str) -> Optional[AgentInfo]:
        return self._agents.get(agent_id)

    def list_by_type(self, agent_type: str) -> list[AgentInfo]:
        ids = self._type_index.get(agent_type, [])
        return [self._agents[aid] for aid in ids if aid in self._agents]

    def list_by_capability(self, capability: str) -> list[AgentInfo]:
        ids = self._capability_index.get(capability, set())
        return [self._agents[aid] for aid in ids if aid in self._agents]

    def list_all(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        info = self._agents.get(agent_id)
        if info:
            info.status = status
            info.last_active = datetime.now(timezone.utc)
            return True
        return False

    def increment_task_count(self, agent_id: str) -> None:
        info = self._agents.get(agent_id)
        if info:
            info.task_count += 1

    def get_capabilities(self, agent_id: str) -> list[str]:
        info = self._agents.get(agent_id)
        return info.capabilities if info else []

    @property
    def agent_count(self) -> int:
        return len(self._agents)
