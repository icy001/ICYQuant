"""AI Control Plane — central orchestration and scheduling for the AI Platform.

The ControlPlane is the brain of the AI Platform. It manages agent lifecycles,
routes tasks to the appropriate agent, enforces scheduling policies, coordinates
shared memory, and governs model selection — all from a single control point.

Responsibilities:
    - Agent lifecycle (create, start, pause, resume, stop, destroy)
    - Task scheduling and prioritization
    - Permission and policy enforcement
    - Global memory coordination
    - Model routing oversight
    - Execution tracking and monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Lifecycle states for managed agents."""
    CREATED = "created"
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATED = "terminated"


class TaskPriority(int, Enum):
    """Priority levels for scheduled tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentRecord:
    """Metadata for an agent managed by the ControlPlane."""
    agent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    agent_type: str = ""
    state: AgentState = AgentState.CREATED
    priority: TaskPriority = TaskPriority.NORMAL
    capabilities: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = 0.0
    task_count: int = 0
    error_count: int = 0


@dataclass
class ControlCommand:
    """Command dispatched by the ControlPlane to an agent."""
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_agent_id: str = ""
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: float = field(default_factory=time.monotonic)
    timeout_sec: float = 60.0


class ControlPlane:
    """Central orchestration point for all AI agents.

    The ControlPlane manages agent lifecycles, dispatches commands, enforces
    scheduling policies, and coordinates shared resources. It serves as the
    single source of truth for agent state across the platform.

    Usage:
        cp = ControlPlane()
        await cp.initialize()
        agent_id = await cp.register_agent(name="market_agent", agent_type="specialized")
        await cp.dispatch(ControlCommand(target_agent_id=agent_id, action="analyze"))
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentRecord] = {}
        self._pending_commands: asyncio.Queue = asyncio.Queue()
        self._command_history: List[ControlCommand] = []
        self._max_history: int = 1000
        self._schedulers: Dict[str, Callable] = {}
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        logger.info("ControlPlane created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ControlPlane initialized")

    async def shutdown(self) -> None:
        self._agents.clear()
        self._command_history.clear()
        self._schedulers.clear()
        self._initialized = False
        logger.info("ControlPlane shutdown complete")

    async def register_agent(self, name: str, agent_type: str, capabilities: Optional[List[str]] = None, permissions: Optional[List[str]] = None) -> str:
        """Register a new agent with the control plane."""
        async with self._lock:
            record = AgentRecord(
                name=name,
                agent_type=agent_type,
                capabilities=capabilities or [],
                permissions=permissions or [],
            )
            self._agents[record.agent_id] = record
            logger.info("ControlPlane: registered agent %s (%s)", name, record.agent_id)
            return record.agent_id

    async def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the control plane."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].state = AgentState.TERMINATED
            del self._agents[agent_id]
            logger.info("ControlPlane: unregistered agent %s", agent_id)
            return True

    async def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.get(agent_id)

    async def list_agents(self, agent_type: Optional[str] = None, state: Optional[AgentState] = None) -> List[AgentRecord]:
        """List agents filtered by type and/or state."""
        async with self._lock:
            agents = list(self._agents.values())
            if agent_type:
                agents = [a for a in agents if a.agent_type == agent_type]
            if state:
                agents = [a for a in agents if a.state == state]
            return agents

    async def update_agent_state(self, agent_id: str, state: AgentState) -> bool:
        """Update an agent's lifecycle state."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            self._agents[agent_id].state = state
            self._agents[agent_id].last_active = time.monotonic()
            return True

    async def dispatch(self, command: ControlCommand) -> str:
        """Dispatch a command to an agent via the control plane."""
        if command.target_agent_id not in self._agents:
            raise ValueError(f"Agent {command.target_agent_id} not registered")
        await self._pending_commands.put(command)
        self._command_history.append(command)
        if len(self._command_history) > self._max_history:
            self._command_history = self._command_history[-self._max_history:]
        logger.info("ControlPlane: dispatched %s -> %s", command.action, command.target_agent_id)
        return command.command_id

    async def pause_agent(self, agent_id: str) -> bool:
        return await self.update_agent_state(agent_id, AgentState.PAUSED)

    async def resume_agent(self, agent_id: str) -> bool:
        return await self.update_agent_state(agent_id, AgentState.IDLE)

    async def stop_agent(self, agent_id: str) -> bool:
        return await self.update_agent_state(agent_id, AgentState.TERMINATED)

    def register_scheduler(self, name: str, scheduler_fn: Callable) -> None:
        """Register a custom scheduling policy."""
        self._schedulers[name] = scheduler_fn

    def get_summary(self) -> Dict[str, Any]:
        async def _summary():
            async with self._lock:
                states = {}
                for a in self._agents.values():
                    states[a.state.value] = states.get(a.state.value, 0) + 1
                return {
                    "initialized": self._initialized,
                    "total_agents": len(self._agents),
                    "agents_by_state": states,
                    "pending_commands": self._pending_commands.qsize(),
                    "registered_schedulers": list(self._schedulers.keys()),
                }
        return asyncio.get_event_loop().run_until_complete(_summary()) if not asyncio.get_event_loop().is_running() else {"initialized": self._initialized, "total_agents": len(self._agents)}
