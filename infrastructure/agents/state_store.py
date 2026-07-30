"""Agent State Store - persistent state management for agents."""

import time
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentLifecycle(Enum):
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentState:
    """Snapshot of an agent's state."""

    agent_id: str
    agent_type: str
    lifecycle: AgentLifecycle = AgentLifecycle.INIT
    started_at: Optional[float] = None
    last_heartbeat: float = field(default_factory=time.time)
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "lifecycle": self.lifecycle.value,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "config": self.config,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "version": self.version,
        }


class StateStore:
    """In-memory state store for agent lifecycle and metrics.

    Can be backed by Redis or DB for production persistence.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._states: Dict[str, AgentState] = {}
        self._snapshots: Dict[str, List[AgentState]] = {}
        self._max_snapshots = 100

    def register(self, agent_id: str, agent_type: str, config: Dict[str, Any] = None) -> AgentState:
        """Register a new agent."""
        state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            config=config or {},
        )
        self._states[agent_id] = state
        logger.info("Agent registered: %s (%s)", agent_id, agent_type)
        return state

    def update_lifecycle(self, agent_id: str, lifecycle: AgentLifecycle) -> bool:
        """Update agent lifecycle state."""
        state = self._states.get(agent_id)
        if not state:
            return False
        old = state.lifecycle
        state.lifecycle = lifecycle
        if lifecycle == AgentLifecycle.RUNNING and state.started_at is None:
            state.started_at = time.time()
        state.last_heartbeat = time.time()
        logger.debug("Agent %s: %s -> %s", agent_id, old.value, lifecycle.value)
        return True

    def heartbeat(self, agent_id: str) -> bool:
        """Record a heartbeat for an agent."""
        state = self._states.get(agent_id)
        if not state:
            return False
        state.last_heartbeat = time.time()
        return True

    def update_metrics(self, agent_id: str, metrics: Dict[str, Any]) -> bool:
        """Update agent metrics."""
        state = self._states.get(agent_id)
        if not state:
            return False
        state.metrics.update(metrics)
        return True

    def get_state(self, agent_id: str) -> Optional[AgentState]:
        """Get agent state."""
        return self._states.get(agent_id)

    def get_all_states(self) -> Dict[str, AgentState]:
        """Get all agent states."""
        return dict(self._states)

    def get_states_by_type(self, agent_type: str) -> List[AgentState]:
        """Get states filtered by agent type."""
        return [s for s in self._states.values() if s.agent_type == agent_type]

    def get_states_by_lifecycle(self, lifecycle: AgentLifecycle) -> List[AgentState]:
        """Get states filtered by lifecycle."""
        return [s for s in self._states.values() if s.lifecycle == lifecycle]

    def snapshot(self, agent_id: str) -> Optional[AgentState]:
        """Create a snapshot of current agent state."""
        state = self._states.get(agent_id)
        if not state:
            return None
        import copy
        snap = copy.deepcopy(state)
        if agent_id not in self._snapshots:
            self._snapshots[agent_id] = []
        self._snapshots[agent_id].append(snap)
        if len(self._snapshots[agent_id]) > self._max_snapshots:
            self._snapshots[agent_id] = self._snapshots[agent_id][-self._max_snapshots:]
        return snap

    def get_snapshots(self, agent_id: str, limit: int = 50) -> List[AgentState]:
        """Get historical snapshots for an agent."""
        snaps = self._snapshots.get(agent_id, [])
        return snaps[-limit:]

    def remove(self, agent_id: str) -> bool:
        """Remove an agent from the store."""
        if agent_id in self._states:
            del self._states[agent_id]
            self._snapshots.pop(agent_id, None)
            return True
        return False

    def export(self) -> Dict[str, Any]:
        """Export all state data."""
        return {
            "states": {k: v.to_dict() for k, v in self._states.items()},
            "timestamp": time.time(),
        }

    @property
    def agent_count(self) -> int:
        return len(self._states)
