"""
Agent registry for agent type registration, discovery, and metadata management.

Maintains a catalog of available agent types with their capabilities,
configuration schemas, and dependency requirements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from shared.exceptions import ICYQuantError

logger = logging.getLogger(__name__)


# ── Registry Types ──


class AgentCapability(str, Enum):
    """Agent capability categories."""

    RESEARCH = "research"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    TRADING = "trading"
    RISK = "risk"
    BACKTEST = "backtest"
    OPTIMIZATION = "optimization"
    COMMUNICATION = "communication"


class AgentType(str, Enum):
    """Registered agent types."""

    RESEARCH_AGENT = "research_agent"
    ANALYSIS_AGENT = "analysis_agent"
    PLANNING_AGENT = "planning_agent"
    EXECUTION_AGENT = "execution_agent"
    MONITORING_AGENT = "monitoring_agent"
    TRADING_AGENT = "trading_agent"
    ORCHESTRATOR = "orchestrator"
    GENERAL = "general"


# ── Agent Descriptor ──


@dataclass
class AgentDescriptor:
    """Metadata describing a registered agent type."""

    agent_type: str
    display_name: str
    description: str
    version: str = "1.0.0"
    capabilities: List[AgentCapability] = field(default_factory=list)
    required_dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    author: str = "ICYQuant"
    tags: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent supports a specific capability."""
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        """Convert descriptor to dictionary."""
        return {
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "capabilities": [c.value for c in self.capabilities],
            "required_dependencies": self.required_dependencies,
            "optional_dependencies": self.optional_dependencies,
            "tags": self.tags,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ── Agent Registry ──


class AgentRegistry:
    """Central registry for agent type discovery and metadata management.

    Provides lookup, filtering, and dependency resolution for agent types.

    Usage:
        registry = AgentRegistry()
        registry.register(AgentDescriptor(...))
        agents = registry.find_by_capability(AgentCapability.RESEARCH)
    """

    def __init__(self) -> None:
        self._registry: Dict[str, AgentDescriptor] = {}
        self._agent_classes: Dict[str, Type] = {}
        self._initialized: bool = False
        logger.info("AgentRegistry created")

    # ── Registration ──

    def register(
        self,
        descriptor: AgentDescriptor,
        agent_class: Optional[Type] = None,
    ) -> None:
        """Register an agent type in the registry.

        Args:
            descriptor: Agent metadata descriptor.
            agent_class: Optional agent implementation class for factory creation.
        """
        if descriptor.agent_type in self._registry:
            logger.warning(f"Overwriting existing registration: {descriptor.agent_type}")

        self._registry[descriptor.agent_type] = descriptor
        if agent_class:
            self._agent_classes[descriptor.agent_type] = agent_class

        logger.info(
            f"Registered agent type: {descriptor.agent_type}",
            extra={"capabilities": [c.value for c in descriptor.capabilities]},
        )

    def unregister(self, agent_type: str) -> bool:
        """Remove an agent type from the registry."""
        removed = self._registry.pop(agent_type, None) is not None
        self._agent_classes.pop(agent_type, None)
        if removed:
            logger.info(f"Unregistered agent type: {agent_type}")
        return removed

    # ── Discovery ──

    def get(self, agent_type: str) -> Optional[AgentDescriptor]:
        """Get agent descriptor by type."""
        return self._registry.get(agent_type)

    def get_class(self, agent_type: str) -> Optional[Type]:
        """Get agent implementation class."""
        return self._agent_classes.get(agent_type)

    def list_all(self) -> List[AgentDescriptor]:
        """Get all registered agent descriptors."""
        return list(self._registry.values())

    def list_types(self) -> List[str]:
        """Get all registered agent type names."""
        return list(self._registry.keys())

    def find_by_capability(self, capability: AgentCapability) -> List[AgentDescriptor]:
        """Find agents supporting a specific capability."""
        return [
            desc
            for desc in self._registry.values()
            if capability in desc.capabilities
        ]

    def find_by_tag(self, tag: str) -> List[AgentDescriptor]:
        """Find agents with a specific tag."""
        return [
            desc
            for desc in self._registry.values()
            if tag in desc.tags
        ]

    def find_by_dependency(self, dependency: str) -> List[AgentDescriptor]:
        """Find agents requiring a specific dependency."""
        return [
            desc
            for desc in self._registry.values()
            if dependency in desc.required_dependencies
            or dependency in desc.optional_dependencies
        ]

    # ── Validation ──

    def validate_dependencies(self, agent_type: str) -> List[str]:
        """Check if all required dependencies are registered.

        Returns list of missing dependency names.
        """
        descriptor = self._registry.get(agent_type)
        if not descriptor:
            raise ICYQuantError(f"Agent type not found: {agent_type}")

        missing = []
        for dep in descriptor.required_dependencies:
            if dep not in self._registry:
                missing.append(dep)
        return missing

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        return {
            "total_registered": len(self._registry),
            "agent_types": list(self._registry.keys()),
            "capability_counts": self._get_capability_counts(),
        }

    def _get_capability_counts(self) -> Dict[str, int]:
        """Count agents per capability."""
        counts: Dict[str, int] = {}
        for desc in self._registry.values():
            for cap in desc.capabilities:
                counts[cap.value] = counts.get(cap.value, 0) + 1
        return counts

    @property
    def is_empty(self) -> bool:
        """Check if registry has any entries."""
        return len(self._registry) == 0
