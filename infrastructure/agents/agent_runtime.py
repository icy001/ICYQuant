"""Agent Runtime - manages agent lifecycle, scheduling, and execution context."""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from infrastructure.agents.message_bus import MessageBus
from infrastructure.agents.task_queue import TaskQueue
from infrastructure.agents.state_store import StateStore, AgentLifecycle

logger = logging.getLogger(__name__)


@dataclass
class RuntimeConfig:
    """Configuration for the agent runtime."""

    name: str = "default"
    tick_interval: float = 1.0  # seconds between agent ticks
    heartbeat_interval: float = 5.0  # seconds between heartbeats
    max_agents: int = 50
    auto_restart: bool = True
    max_restarts: int = 3
    daemon: bool = True


class AgentRuntime:
    """Manages the execution of multiple agents.

    Handles lifecycle, scheduling, heartbeats, and resource allocation.
    """

    def __init__(self, config: RuntimeConfig = None):
        self.config = config or RuntimeConfig()
        self.message_bus = MessageBus(self.config.name)
        self.task_queue = TaskQueue(self.config.name)
        self.state_store = StateStore(self.config.name)
        self._agents: Dict[str, Any] = {}  # agent_id -> agent instance
        self._tick_callbacks: Dict[str, Callable] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._restart_counts: Dict[str, int] = {}
        self._start_time: Optional[float] = None

    def register_agent(self, agent: Any) -> str:
        """Register an agent with the runtime."""
        with self._lock:
            if len(self._agents) >= self.config.max_agents:
                raise RuntimeError(f"Max agents ({self.config.max_agents}) reached")

            agent_id = agent.name
            self._agents[agent_id] = agent
            self.state_store.register(
                agent_id=agent_id,
                agent_type=agent.agent_type,
                config=getattr(agent, 'config', {}),
            )
            # Wire agent to runtime infrastructure
            agent.message_bus = self.message_bus
            agent.task_queue = self.task_queue
            agent.state_store = self.state_store
            # Subscribe to messages for this agent
            self.message_bus.subscribe(agent_id, agent.handle_message)
            logger.info("Agent registered in runtime: %s", agent_id)
            return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the runtime."""
        with self._lock:
            agent = self._agents.pop(agent_id, None)
            if agent:
                self.state_store.remove(agent_id)
                self._tick_callbacks.pop(agent_id, None)
                self._restart_counts.pop(agent_id, None)
                logger.info("Agent unregistered: %s", agent_id)
                return True
        return False

    def register_tick(self, agent_id: str, callback: Callable) -> None:
        """Register a tick callback for periodic agent execution."""
        self._tick_callbacks[agent_id] = callback

    def start(self) -> None:
        """Start the agent runtime."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"agent-runtime-{self.config.name}",
            daemon=self.config.daemon,
        )
        self._thread.start()
        logger.info("Agent runtime '%s' started", self.config.name)

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the agent runtime gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout)

        for agent_id in list(self._agents.keys()):
            self.state_store.update_lifecycle(agent_id, AgentLifecycle.STOPPED)

        logger.info("Agent runtime '%s' stopped", self.config.name)

    def _run_loop(self) -> None:
        """Main runtime loop - tick agents and process tasks."""
        last_heartbeat = time.time()
        while self._running:
            try:
                # Process pending tasks
                while True:
                    task = self.task_queue.get_next()
                    if task is None:
                        break
                    self._execute_task(task)

                # Tick agents
                for agent_id, callback in list(self._tick_callbacks.items()):
                    try:
                        callback()
                    except Exception:
                        logger.exception("Tick error for agent %s", agent_id)
                        if self.config.auto_restart:
                            self._maybe_restart(agent_id)

                # Heartbeat check
                now = time.time()
                if now - last_heartbeat >= self.config.heartbeat_interval:
                    for agent_id, agent in list(self._agents.items()):
                        if hasattr(agent, 'heartbeat'):
                            try:
                                agent.heartbeat()
                            except Exception:
                                logger.warning("Agent %s heartbeat failed", agent_id)
                    last_heartbeat = now

            except Exception:
                logger.exception("Runtime loop error")

            time.sleep(self.config.tick_interval)

    def _execute_task(self, task: Any) -> None:
        """Execute a task, routing to the appropriate agent."""
        agent = self._agents.get(task.agent)
        if agent is None:
            self.task_queue.fail(task.task_id, f"Agent {task.agent} not found")
            return

        try:
            if hasattr(agent, 'execute_task'):
                result = agent.execute_task(task)
                self.task_queue.complete(task.task_id, result)
            else:
                self.task_queue.complete(task.task_id, None)
        except Exception as e:
            self.task_queue.fail(task.task_id, str(e))

    def _maybe_restart(self, agent_id: str) -> None:
        """Attempt to restart a failed agent."""
        count = self._restart_counts.get(agent_id, 0)
        if count >= self.config.max_restarts:
            logger.error("Agent %s exceeded max restarts (%d)", agent_id, self.config.max_restarts)
            self.state_store.update_lifecycle(agent_id, AgentLifecycle.ERROR)
            return

        self._restart_counts[agent_id] = count + 1
        logger.warning("Restarting agent %s (attempt %d/%d)",
                       agent_id, count + 1, self.config.max_restarts)

    def get_status(self) -> Dict[str, Any]:
        """Get overall runtime status."""
        states = self.state_store.get_all_states()
        agent_statuses = {}
        for agent_id, state in states.items():
            agent_statuses[agent_id] = {
                "type": state.agent_type,
                "lifecycle": state.lifecycle.value,
                "uptime": time.time() - state.started_at if state.started_at else 0,
                "metrics": state.metrics,
            }

        return {
            "runtime": self.config.name,
            "running": self._running,
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "agent_count": len(self._agents),
            "messages": self.message_bus.message_count,
            "pending_tasks": self.task_queue.pending_count,
            "agents": agent_statuses,
        }

    @property
    def agent_count(self) -> int:
        return len(self._agents)
