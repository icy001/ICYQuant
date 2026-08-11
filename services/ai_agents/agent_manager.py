"""
ICYQuant Agent Manager — lifecycle management for all agents.

Manages agent creation, initialization, health monitoring, shutdown,
and coordination with the runtime and registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentManagerConfig:
    max_agents: int = 50
    health_check_interval_seconds: int = 30
    auto_restart_on_failure: bool = True
    max_restarts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentManager:
    """Lifecycle manager for all agents in the system.

    Responsibilities:
        - Agent creation and initialization
        - Health monitoring and auto-restart
        - Graceful shutdown coordination
        - Dependency ordering for agent startup
    """

    def __init__(self, config: Optional[AgentManagerConfig] = None,
                 registry: Any = None, runtime: Any = None) -> None:
        self._config = config or AgentManagerConfig()
        self._registry = registry
        self._runtime = runtime
        self._agent_instances: dict[str, Any] = {}
        self._restart_counts: dict[str, int] = {}
        self._total_created = 0

    async def create_agent(self, agent_cls: type, agent_id: str, agent_type: str,
                           name: str = "", capabilities: Optional[list[str]] = None,
                           **kwargs: Any) -> Any:
        """Create and initialize an agent instance."""
        if len(self._agent_instances) >= self._config.max_agents:
            raise RuntimeError(f"Max agents ({self._config.max_agents}) reached")

        if self._runtime is not None:
            agent = await self._runtime.spawn_agent(
                agent_cls, agent_id=agent_id, **kwargs
            )
        else:
            agent = agent_cls(agent_id=agent_id, **kwargs)

        self._agent_instances[agent_id] = agent
        self._restart_counts[agent_id] = 0
        self._total_created += 1

        if self._registry is not None:
            self._registry.register(
                agent_id=agent_id,
                name=name or agent_type,
                agent_type=agent_type,
                capabilities=capabilities or [],
            )

        logger.info("Created agent %s [%s]", agent_id, agent_type)
        return agent

    def get_agent(self, agent_id: str) -> Optional[Any]:
        return self._agent_instances.get(agent_id)

    def list_agents(self) -> list[str]:
        return list(self._agent_instances.keys())

    def remove_agent(self, agent_id: str) -> bool:
        if agent_id in self._agent_instances:
            del self._agent_instances[agent_id]
            self._restart_counts.pop(agent_id, None)
            if self._registry:
                self._registry.unregister(agent_id)
            return True
        return False

    async def restart_agent(self, agent_id: str) -> Optional[Any]:
        """Attempt to restart a failed agent."""
        count = self._restart_counts.get(agent_id, 0)
        if count >= self._config.max_restarts:
            logger.warning("Agent %s exceeded max restarts (%d)", agent_id, self._config.max_restarts)
            return None

        agent = self._agent_instances.get(agent_id)
        if agent and hasattr(agent, 'restart'):
            await agent.restart()
            self._restart_counts[agent_id] = count + 1
            logger.info("Restarted agent %s (attempt %d/%d)",
                        agent_id, count + 1, self._config.max_restarts)
            return agent
        return None

    async def shutdown_all(self) -> int:
        """Gracefully shutdown all agents."""
        count = 0
        for agent_id, agent in list(self._agent_instances.items()):
            try:
                if hasattr(agent, 'shutdown'):
                    await agent.shutdown()
                count += 1
            except Exception as exc:
                logger.error("Error shutting down agent %s: %s", agent_id, exc)
            finally:
                self.remove_agent(agent_id)
        logger.info("Shutdown %d agents", count)
        return count

    @property
    def agent_count(self) -> int:
        return len(self._agent_instances)

    @property
    def total_created(self) -> int:
        return self._total_created
