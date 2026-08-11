"""Agent SDK — unified developer interface for registering custom agents in the collaboration platform.

Provides a decorator-based API that allows developers to declare agent
capabilities, permissions, and metadata without touching the framework core.

Usage:
    from services.ai_agent.collaboration.sdk import agent

    @agent(name="my_custom_agent", capability="custom.analysis", priority=3)
    class MyCustomAgent(SpecializedAgent):
        ...

    agent_sdk = AgentSDK()
    await agent_sdk.register_decorated()
"""

from __future__ import annotations

import functools
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger(__name__)


# ── Decorator definition ──

@dataclass
class AgentDeclaration:
    """Metadata collected by the @agent decorator.

    Attributes:
        name: The agent's unique identifier.
        capability: The primary capability this agent provides.
        priority: Priority for task assignment (higher = preferred).
        description: Human-readable description.
        tags: Search/filter tags.
        permissions: Required permissions.
        cls: The decorated agent class.
    """

    name: str
    capability: str
    priority: int = 1
    description: str = ""
    tags: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    cls: Optional[Type] = None


def agent(
    name: str,
    capability: str,
    priority: int = 1,
    description: str = "",
    tags: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
) -> Callable:
    """Decorator that registers a class as an Agent.

    Args:
        name: The agent's unique identifier in the registry.
        capability: Primary capability (e.g. "market.chart", "research.backtest").
        priority: Assignment priority (1-10, higher = preferred).
        description: Human-readable purpose description.
        tags: Search/filter tags for discovery.
        permissions: Required permissions for this agent.

    Returns:
        A decorator that attaches _agent_declaration to the class.

    Example:
        @agent(name="sentiment_agent", capability="nlp.sentiment", priority=2,
               tags=["nlp", "news"], permissions=["nlp.execute"])
        class SentimentAgent:
            ...
    """

    def decorator(cls: Type) -> Type:
        declaration = AgentDeclaration(
            name=name,
            capability=capability,
            priority=priority,
            description=description,
            tags=tags or [],
            permissions=permissions or [],
            cls=cls,
        )
        setattr(cls, "_agent_declaration", declaration)
        logger.info(
            "Agent class decorated: %s (name=%s, capability=%s, priority=%d)",
            cls.__name__, name, capability, priority,
        )
        return cls

    return decorator


# ── AgentSDK ──

class AgentSDK:
    """Facade for programmatic agent registration and lifecycle management.

    The SDK bridges the gap between developer-authored agent classes
    and the collaboration platform's core services (AgentRegistry,
    AgentDiscovery, AgentRouter, CoordinatorAgent).

    Usage:
        sdk = AgentSDK(registry, discovery, monitor)
        await sdk.initialize()

        # Register decorated classes
        from my_package.agents import MyAgent
        await sdk.register(MyAgent)

        # Or scan a module
        await sdk.scan_module("my_package.agents")

        # Register manually
        await sdk.register_class("custom_agent", MyAgent, capability="custom.ops")
    """

    def __init__(
        self,
        registry: Any = None,   # AgentRegistry
        discovery: Any = None,  # AgentDiscovery
        monitor: Any = None,    # AgentMonitor
    ) -> None:
        """Initialize the Agent SDK.

        Args:
            registry: An AgentRegistry instance.
            discovery: An AgentDiscovery instance.
            monitor: An AgentMonitor instance.
        """
        self._registry = registry
        self._discovery = discovery
        self._monitor = monitor

        self._declarations: Dict[str, AgentDeclaration] = {}
        self._instance_cache: Dict[str, Any] = {}
        self._initialized: bool = False
        logger.info("AgentSDK created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the SDK."""
        if self._initialized:
            logger.warning("AgentSDK already initialized")
            return
        self._initialized = True
        logger.info("AgentSDK initialized")

    async def shutdown(self) -> None:
        """Shut down the SDK and clear registrations."""
        self._declarations.clear()
        self._instance_cache.clear()
        self._initialized = False
        logger.info("AgentSDK shutdown complete")

    # ── Registration ──

    async def register_decorated(self, *classes: Type) -> List[str]:
        """Register one or more @agent-decorated classes.

        Args:
            classes: Agent classes decorated with @agent.

        Returns:
            List of registered agent names.
        """
        registered: List[str] = []

        for cls in classes:
            declaration: Optional[AgentDeclaration] = getattr(cls, "_agent_declaration", None)
            if declaration is None:
                logger.warning("Class %s is not decorated with @agent, skipping", cls.__name__)
                continue

            await self._do_register(declaration, cls)
            registered.append(declaration.name)

        return registered

    async def register_class(
        self,
        name: str,
        cls: Type,
        capability: str,
        priority: int = 1,
        description: str = "",
        tags: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
    ) -> str:
        """Register an agent class programmatically.

        Args:
            name: Unique agent name.
            cls: The agent class.
            capability: Primary capability.
            priority: Assignment priority.
            description: Human-readable description.
            tags: Search/filter tags.
            permissions: Required permissions.

        Returns:
            The registered agent name.
        """
        declaration = AgentDeclaration(
            name=name,
            capability=capability,
            priority=priority,
            description=description,
            tags=tags or [],
            permissions=permissions or [],
            cls=cls,
        )
        await self._do_register(declaration, cls)
        return name

    async def scan_module(self, module_path: str) -> List[str]:
        """Scan a Python module for @agent-decorated classes and register them.

        Args:
            module_path: Dotted path to the module (e.g. "my_package.agents").

        Returns:
            List of registered agent names.
        """
        import importlib

        try:
            module = importlib.import_module(module_path)
        except ImportError:
            logger.error("Failed to import module: %s", module_path)
            return []

        registered: List[str] = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            declaration = getattr(obj, "_agent_declaration", None)
            if declaration is not None:
                await self._do_register(declaration, obj)
                registered.append(declaration.name)

        logger.info("Scanned module %s, registered %d agents", module_path, len(registered))
        return registered

    async def _do_register(self, declaration: AgentDeclaration, cls: Type) -> None:
        """Internal: perform registration across all platform services.

        Args:
            declaration: The agent declaration.
            cls: The agent class.
        """
        self._declarations[declaration.name] = declaration

        # Register with core registry if available
        if self._registry:
            await self._registry.register(
                name=declaration.name,
                capability=declaration.capability,
                priority=declaration.priority,
                description=declaration.description,
                tags=declaration.tags,
                permissions=declaration.permissions,
                cls=cls,
            )

        # Register with monitor if available
        if self._monitor:
            self._monitor.register_agent(declaration.name)

        logger.info(
            "Agent registered via SDK: name=%s capability=%s priority=%d",
            declaration.name, declaration.capability, declaration.priority,
        )

    # ── Instance Management ──

    async def create_instance(self, agent_name: str, **kwargs) -> Any:
        """Create an instance of a registered agent.

        Args:
            agent_name: The registered agent name.
            **kwargs: Constructor arguments.

        Returns:
            The agent instance.

        Raises:
            ValueError: If the agent is not registered.
        """
        declaration = self._declarations.get(agent_name)
        if declaration is None:
            raise ValueError(f"Agent not registered: {agent_name}")

        if declaration.cls is None:
            raise ValueError(f"Agent class not found for: {agent_name}")

        instance = declaration.cls(**kwargs)
        self._instance_cache[agent_name] = instance
        logger.info("Agent instance created: %s", agent_name)
        return instance

    def get_instance(self, agent_name: str) -> Optional[Any]:
        """Get a cached agent instance.

        Args:
            agent_name: The agent name.

        Returns:
            The agent instance or None.
        """
        return self._instance_cache.get(agent_name)

    # ── Queries ──

    def list_registered(self) -> List[Dict[str, Any]]:
        """List all registered agent declarations.

        Returns:
            List of agent declaration summaries.
        """
        return [
            {
                "name": d.name,
                "capability": d.capability,
                "priority": d.priority,
                "description": d.description,
                "tags": d.tags,
                "permissions": d.permissions,
                "class": d.cls.__name__ if d.cls else None,
            }
            for d in self._declarations.values()
        ]

    def get_declaration(self, agent_name: str) -> Optional[AgentDeclaration]:
        """Get the declaration for a registered agent.

        Args:
            agent_name: The agent name.

        Returns:
            AgentDeclaration or None.
        """
        return self._declarations.get(agent_name)

    @property
    def registered_count(self) -> int:
        """Return the number of registered agent declarations."""
        return len(self._declarations)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the SDK state.

        Returns:
            Dict with initialization and registration counts.
        """
        return {
            "initialized": self._initialized,
            "registered_agents": len(self._declarations),
            "cached_instances": len(self._instance_cache),
            "names": sorted(self._declarations.keys()),
        }
