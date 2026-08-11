"""
Agent factory for constructing agent instances from registry descriptors.

Provides dependency injection, configuration application,
and lifecycle management for agent creation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from services.ai_agent.agent_registry import AgentDescriptor, AgentRegistry
from services.ai_agent.agent_repository import AgentRecord, AgentRepository
from shared.exceptions import ICYQuantError

logger = logging.getLogger(__name__)


# ── Factory Types ──


@dataclass
class AgentBuildContext:
    """Context for building a new agent instance."""

    agent_type: str
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    parent_agent_id: Optional[str] = None


# ── Agent Factory ──


class AgentFactory:
    """Factory for creating and configuring agent instances.

    Handles dependency resolution, configuration merging,
    and lifecycle initialization.

    Usage:
        factory = AgentFactory(registry, repository)
        agent = factory.create(AgentBuildContext(
            agent_type="research_agent",
            name="my_researcher",
        ))
    """

    def __init__(
        self,
        registry: AgentRegistry,
        repository: Optional[AgentRepository] = None,
    ) -> None:
        self.registry = registry
        self.repository = repository or AgentRepository()
        self._builders: Dict[str, Any] = {}  # agent_type -> builder callable
        logger.info("AgentFactory initialized")

    # ── Builder Registration ──

    def register_builder(self, agent_type: str, builder: Any) -> None:
        """Register a custom builder for an agent type.

        Args:
            agent_type: The agent type identifier.
            builder: Callable that accepts config dict and returns agent instance.
        """
        self._builders[agent_type] = builder
        logger.info(f"Registered builder for: {agent_type}")

    # ── Creation ──

    def create(self, ctx: AgentBuildContext) -> Any:
        """Create and configure a new agent instance.

        Args:
            ctx: Build context with type, name, config, and overrides.

        Returns:
            Configured agent instance.

        Raises:
            ICYQuantError: If agent type is not registered or creation fails.
        """
        descriptor = self.registry.get(ctx.agent_type)
        if not descriptor:
            raise ICYQuantError(f"Unknown agent type: {ctx.agent_type}")

        logger.info(
            f"Creating agent of type: {ctx.agent_type}",
            extra={"name": ctx.name},
        )

        # Merge configurations
        merged_config = self._merge_config(descriptor.default_config, ctx.config, ctx.overrides)

        # Use registered builder or default construction
        agent = self._build_agent(descriptor, merged_config, ctx)

        # Create persistent record
        record = AgentRecord(
            agent_id=getattr(agent, "agent_id", ""),
            agent_type=ctx.agent_type,
            name=ctx.name,
            config=merged_config,
            metadata=ctx.metadata,
            tags=ctx.tags,
        )
        self.repository.save(record)

        logger.info(f"Created agent: {record.agent_id} ({ctx.name})")
        return agent

    def _merge_config(
        self,
        default: Dict[str, Any],
        user: Dict[str, Any],
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge configuration layers: default < user < overrides."""
        merged = dict(default)
        merged.update(user)
        merged.update(overrides)
        return merged

    def _build_agent(
        self,
        descriptor: AgentDescriptor,
        config: Dict[str, Any],
        ctx: AgentBuildContext,
    ) -> Any:
        """Build agent instance using registered builder or default."""
        builder = self._builders.get(ctx.agent_type)
        if builder:
            return builder(config, ctx)

        # Default: create from registered class
        agent_class = self.registry.get_class(ctx.agent_type)
        if agent_class:
            try:
                return agent_class(config=config, name=ctx.name)
            except Exception as e:
                raise ICYQuantError(f"Failed to instantiate agent [{ctx.agent_type}]: {e}") from e

        raise ICYQuantError(f"No builder or class registered for agent type: {ctx.agent_type}")

    # ── Batch Creation ──

    def create_batch(self, contexts: List[AgentBuildContext]) -> List[Any]:
        """Create multiple agent instances."""
        agents = []
        for ctx in contexts:
            try:
                agent = self.create(ctx)
                agents.append(agent)
            except Exception as e:
                logger.error(f"Failed to create agent [{ctx.name}]: {e}")
                raise
        return agents

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get factory summary."""
        return {
            "registered_builders": list(self._builders.keys()),
            "registry_size": len(self.registry.list_types()),
            "repository_summary": self.repository.get_summary(),
        }
