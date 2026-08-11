"""Agent Lifecycle Manager — manages the full lifecycle of all AI agents.

The LifecycleManager provides standardized create/start/pause/resume/stop/destroy
operations for all agents registered in the platform. It enforces state transitions,
handles graceful shutdown, and coordinates with the ControlPlane for scheduling.

State Machine:
    CREATED -> INITIALIZING -> IDLE <-> BUSY
                  |                |
                  v                v
              TERMINATED       PAUSED -> IDLE
                  ^                |
                  |                v
              ERROR <---------- ERROR
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
    """Agent lifecycle states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"


# Valid state transitions
_VALID_TRANSITIONS: Dict[LifecycleState, List[LifecycleState]] = {
    LifecycleState.CREATED: [LifecycleState.INITIALIZING, LifecycleState.DESTROYED],
    LifecycleState.INITIALIZING: [LifecycleState.IDLE, LifecycleState.ERROR],
    LifecycleState.IDLE: [LifecycleState.BUSY, LifecycleState.PAUSED, LifecycleState.STOPPING, LifecycleState.ERROR],
    LifecycleState.BUSY: [LifecycleState.IDLE, LifecycleState.PAUSED, LifecycleState.ERROR],
    LifecycleState.PAUSED: [LifecycleState.IDLE, LifecycleState.STOPPING, LifecycleState.ERROR],
    LifecycleState.STOPPING: [LifecycleState.STOPPED, LifecycleState.ERROR],
    LifecycleState.STOPPED: [LifecycleState.DESTROYED],
    LifecycleState.ERROR: [LifecycleState.IDLE, LifecycleState.STOPPING, LifecycleState.DESTROYED],
    LifecycleState.DESTROYED: [],
}


@dataclass
class LifecycleEvent:
    """Record of a state transition event."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    from_state: Optional[LifecycleState] = None
    to_state: LifecycleState = LifecycleState.CREATED
    reason: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class LifecycleRecord:
    """Full lifecycle tracking for a single agent."""
    agent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    agent_type: str = ""
    state: LifecycleState = LifecycleState.CREATED
    created_at: float = field(default_factory=time.monotonic)
    last_transition: float = 0.0
    history: List[LifecycleEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LifecycleManager:
    """Manages agent lifecycle with enforced state transitions.

    Provides the standard lifecycle operations (create, initialize, start, pause,
    resume, stop, destroy) for all agents in the platform. Ensures that only
    valid state transitions are performed.

    Usage:
        lm = LifecycleManager()
        await lm.initialize()
        agent_id = await lm.create_agent("market_agent", "specialized")
        await lm.initialize_agent(agent_id)
        await lm.start_agent(agent_id)
        await lm.stop_agent(agent_id)
    """

    def __init__(self, max_history: int = 100) -> None:
        self._agents: Dict[str, LifecycleRecord] = {}
        self._max_history = max_history
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        logger.info("LifecycleManager created (max_history=%d)", max_history)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("LifecycleManager initialized")

    async def shutdown(self) -> None:
        """Stop all agents gracefully before shutdown."""
        async with self._lock:
            for agent_id, record in list(self._agents.items()):
                if record.state not in (LifecycleState.STOPPED, LifecycleState.DESTROYED):
                    try:
                        await self._transition(agent_id, LifecycleState.STOPPING, "platform_shutdown")
                        await self._transition(agent_id, LifecycleState.STOPPED, "platform_shutdown")
                    except Exception as e:
                        logger.error("Failed to stop agent %s during shutdown: %s", agent_id, e)
            self._agents.clear()
        self._initialized = False
        logger.info("LifecycleManager shutdown complete")

    async def create_agent(self, name: str, agent_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new agent record."""
        async with self._lock:
            record = LifecycleRecord(name=name, agent_type=agent_type, metadata=metadata or {})
            self._agents[record.agent_id] = record
            logger.info("Lifecycle: created agent %s (%s)", name, record.agent_id)
            return record.agent_id

    async def initialize_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.INITIALIZING, "init_requested") and await self._transition(agent_id, LifecycleState.IDLE, "init_complete")

    async def start_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.BUSY, "task_started")

    async def complete_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.IDLE, "task_completed")

    async def pause_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.PAUSED, "pause_requested")

    async def resume_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.IDLE, "resume_requested")

    async def stop_agent(self, agent_id: str) -> bool:
        if await self._transition(agent_id, LifecycleState.STOPPING, "stop_requested"):
            return await self._transition(agent_id, LifecycleState.STOPPED, "stop_complete")
        return False

    async def destroy_agent(self, agent_id: str) -> bool:
        return await self._transition(agent_id, LifecycleState.DESTROYED, "destroy_requested")

    async def mark_error(self, agent_id: str, reason: str = "") -> bool:
        return await self._transition(agent_id, LifecycleState.ERROR, reason)

    async def _transition(self, agent_id: str, to_state: LifecycleState, reason: str) -> bool:
        """Perform a state transition with validation."""
        async with self._lock:
            if agent_id not in self._agents:
                logger.warning("Lifecycle: agent %s not found", agent_id)
                return False

            record = self._agents[agent_id]
            valid = _VALID_TRANSITIONS.get(record.state, [])
            if to_state not in valid:
                logger.warning("Lifecycle: invalid transition %s -> %s for agent %s", record.state.value, to_state.value, agent_id)
                return False

            event = LifecycleEvent(
                agent_id=agent_id,
                from_state=record.state,
                to_state=to_state,
                reason=reason,
            )
            record.state = to_state
            record.last_transition = event.timestamp
            record.history.append(event)
            if len(record.history) > self._max_history:
                record.history = record.history[-self._max_history:]

            logger.info("Lifecycle: agent %s %s -> %s (%s)", agent_id, event.from_state.value if event.from_state else "none", to_state.value, reason)
            return True

    async def get_agent(self, agent_id: str) -> Optional[LifecycleRecord]:
        return self._agents.get(agent_id)

    async def list_by_state(self, state: LifecycleState) -> List[LifecycleRecord]:
        async with self._lock:
            return [r for r in self._agents.values() if r.state == state]

    def get_summary(self) -> Dict[str, Any]:
        states: Dict[str, int] = {}
        for r in self._agents.values():
            states[r.state.value] = states.get(r.state.value, 0) + 1
        return {
            "initialized": self._initialized,
            "total_agents": len(self._agents),
            "by_state": states,
        }
