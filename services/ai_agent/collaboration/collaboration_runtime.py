"""Collaboration Runtime — runtime environment configuration and bootstrap for multi-agent collaboration.

Pipeline:
    RuntimeConfig (configuration)
        -> CollaborationRuntime.initialize()
        -> Bootstrap environment (limits, timeouts, resource pools)
        -> Runtime ready for agent execution
        -> CollaborationRuntime.shutdown()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class RuntimeConfig:
    """Configuration for the multi-agent collaboration runtime.

    Attributes:
        max_concurrent_agents: Maximum number of agents executing concurrently.
        agent_timeout_seconds: Default timeout for individual agent execution.
        max_queue_size: Maximum size of the message queue.
        coordination_timeout_seconds: Timeout for coordinator planning cycles.
        consensus_timeout_seconds: Timeout for consensus-reaching processes.
        negotiation_rounds: Maximum rounds for agent negotiation.
        memory_max_segments: Maximum number of shared memory segments.
        blackboard_max_entries: Maximum number of blackboard entries.
        monitor_interval_seconds: Interval between agent health checks.
        enable_auto_recovery: Whether to automatically recover failed agents.
        enable_telemetry: Whether to enable distributed tracing.
        enable_diagnostics: Whether to enable performance diagnostics.
    """

    max_concurrent_agents: int = 20
    agent_timeout_seconds: float = 60.0
    max_queue_size: int = 10000
    coordination_timeout_seconds: float = 30.0
    consensus_timeout_seconds: float = 15.0
    negotiation_rounds: int = 3
    memory_max_segments: int = 1000
    blackboard_max_entries: int = 500
    monitor_interval_seconds: float = 5.0
    enable_auto_recovery: bool = True
    enable_telemetry: bool = True
    enable_diagnostics: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as a dictionary."""
        return {
            "max_concurrent_agents": self.max_concurrent_agents,
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "max_queue_size": self.max_queue_size,
            "coordination_timeout_seconds": self.coordination_timeout_seconds,
            "consensus_timeout_seconds": self.consensus_timeout_seconds,
            "negotiation_rounds": self.negotiation_rounds,
            "memory_max_segments": self.memory_max_segments,
            "blackboard_max_entries": self.blackboard_max_entries,
            "monitor_interval_seconds": self.monitor_interval_seconds,
            "enable_auto_recovery": self.enable_auto_recovery,
            "enable_telemetry": self.enable_telemetry,
            "enable_diagnostics": self.enable_diagnostics,
        }


class CollaborationRuntime:
    """Runtime environment for multi-agent collaboration.

    Bootstraps the execution environment including resource pools, concurrency
    controls, and global runtime settings used by all collaboration components.

    Supports:
        - Resource pool initialization
        - Concurrency limiting
        - Global timeout enforcement
        - Runtime state management

    Usage:
        runtime = CollaborationRuntime(config)
        await runtime.initialize()
        # ... agents execute within this runtime ...
        await runtime.shutdown()
    """

    def __init__(self, config: RuntimeConfig) -> None:
        """Initialize the collaboration runtime.

        Args:
            config: Runtime configuration parameters.
        """
        self._config: RuntimeConfig = config
        self._initialized: bool = False
        self._active_agents: int = 0
        self._total_tasks_completed: int = 0
        logger.info("CollaborationRuntime created with max_concurrent_agents=%d",
                     config.max_concurrent_agents)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the runtime environment."""
        if self._initialized:
            logger.warning("CollaborationRuntime already initialized")
            return

        self._initialized = True
        self._active_agents = 0
        self._total_tasks_completed = 0
        logger.info("CollaborationRuntime initialized")

    async def shutdown(self) -> None:
        """Shut down the runtime and clean up resources."""
        if not self._initialized:
            return

        self._initialized = False
        logger.info("CollaborationRuntime shutdown complete "
                     "(total_tasks=%d)", self._total_tasks_completed)

    # ── Concurrency ──

    def can_accept_agent(self) -> bool:
        """Check whether a new agent can be started.

        Returns:
            True if the number of active agents is below the configured maximum.
        """
        return self._active_agents < self._config.max_concurrent_agents

    def agent_started(self) -> None:
        """Record that an agent has started execution."""
        self._active_agents += 1
        logger.debug("Agent started (active=%d/%d)",
                     self._active_agents, self._config.max_concurrent_agents)

    def agent_finished(self) -> None:
        """Record that an agent has finished execution."""
        self._active_agents = max(0, self._active_agents - 1)
        self._total_tasks_completed += 1
        logger.debug("Agent finished (active=%d, total=%d)",
                     self._active_agents, self._total_tasks_completed)

    # ── Properties ──

    @property
    def config(self) -> RuntimeConfig:
        """Return the runtime configuration."""
        return self._config

    @property
    def active_agents(self) -> int:
        """Return the current number of active agents."""
        return self._active_agents

    @property
    def is_initialized(self) -> bool:
        """Return whether the runtime is initialized."""
        return self._initialized

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the runtime state.

        Returns:
            Dict with initialization status, active agents, and task count.
        """
        return {
            "initialized": self._initialized,
            "active_agents": self._active_agents,
            "max_concurrent_agents": self._config.max_concurrent_agents,
            "total_tasks_completed": self._total_tasks_completed,
            "can_accept_agent": self.can_accept_agent(),
        }
