"""Platform SDK — developer SDK for building and extending the AI Platform.

The PlatformSDK provides a unified developer interface for building custom
agents, tools, plugins, and extensions for the ICYQuant AI Platform. It
abstracts away platform internals and provides a clean, declarative API.

SDK capabilities:
    - Agent development with @agent decorator
    - Tool registration
    - Plugin system
    - Module auto-discovery
    - Configuration management
    - Testing utilities
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    """Types of plugins supported by the platform."""
    AGENT = "agent"
    TOOL = "tool"
    GUARDRAIL = "guardrail"
    POLICY = "policy"
    ADAPTER = "adapter"
    MIDDLEWARE = "middleware"


@dataclass
class PluginMetadata:
    """Metadata for a registered plugin."""
    name: str
    plugin_type: PluginType
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""


@dataclass
class AgentDeclaration:
    """Declaration of an agent registered via the SDK."""
    name: str
    agent_type: str
    capability: str = ""
    description: str = ""
    priority: int = 0
    permissions: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)


class PlatformSDK:
    """Developer SDK for building and extending the AI Platform.

    Provides decorators, registration APIs, and utilities for building
    custom agents, tools, and plugins.

    Usage:
        sdk = PlatformSDK()
        await sdk.initialize()

        @sdk.agent(name="custom_agent", capability="custom.analysis")
        class CustomAgent:
            async def analyze(self, data): ...

        sdk.register_tool("my_tool", my_tool_fn)
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentDeclaration] = {}
        self._agent_classes: Dict[str, Type] = {}
        self._tools: Dict[str, Callable] = {}
        self._plugins: Dict[str, PluginMetadata] = {}
        self._initialized: bool = False
        logger.info("PlatformSDK created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PlatformSDK initialized")

    async def shutdown(self) -> None:
        self._agents.clear()
        self._agent_classes.clear()
        self._tools.clear()
        self._plugins.clear()
        self._initialized = False
        logger.info("PlatformSDK shutdown complete")

    def agent(self, name: str = "", agent_type: str = "custom", capability: str = "", description: str = "", priority: int = 0, permissions: Optional[List[str]] = None, tools: Optional[List[str]] = None) -> Callable:
        """Decorator to register an agent class.

        Usage:
            @sdk.agent(name="market_agent", capability="market.analysis")
            class MarketAgent:
                async def analyze(self, context): ...
        """
        def decorator(cls: Type) -> Type:
            agent_name = name or cls.__name__.lower()
            declaration = AgentDeclaration(
                name=agent_name,
                agent_type=agent_type,
                capability=capability,
                description=description,
                priority=priority,
                permissions=permissions or [],
                tools=tools or [],
            )
            self._agents[agent_name] = declaration
            self._agent_classes[agent_name] = cls
            logger.info("PlatformSDK: registered agent '%s' (%s)", agent_name, capability)
            return cls
        return decorator

    def tool(self, name: str = "", description: str = "") -> Callable:
        """Decorator to register a tool function.

        Usage:
            @sdk.tool(name="get_price", description="Get current price for a symbol")
            async def get_price(symbol: str) -> float: ...
        """
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            self._tools[tool_name] = fn
            logger.info("PlatformSDK: registered tool '%s'", tool_name)
            return fn
        return decorator

    def register_tool(self, name: str, fn: Callable) -> None:
        """Register a tool function programmatically."""
        self._tools[name] = fn
        logger.info("PlatformSDK: registered tool '%s'", name)

    def register_plugin(self, metadata: PluginMetadata) -> None:
        """Register a plugin."""
        self._plugins[metadata.name] = metadata
        logger.info("PlatformSDK: registered plugin '%s' (%s)", metadata.name, metadata.plugin_type.value)

    def get_agent(self, name: str) -> Optional[AgentDeclaration]:
        """Get an agent declaration by name."""
        return self._agents.get(name)

    def get_agent_class(self, name: str) -> Optional[Type]:
        """Get an agent class by name."""
        return self._agent_classes.get(name)

    def list_agents(self) -> List[AgentDeclaration]:
        """List all registered agents."""
        return list(self._agents.values())

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return sorted(self._tools.keys())

    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[PluginMetadata]:
        """List registered plugins, optionally filtered by type."""
        plugins = list(self._plugins.values())
        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type == plugin_type]
        return plugins

    async def discover_modules(self, package_path: str) -> int:
        """Auto-discover and load agent/tool modules from a package path.

        Scans the given directory for Python modules and imports them,
        triggering any @agent or @tool decorators.
        """
        discovered = 0
        if not os.path.isdir(package_path):
            logger.warning("PlatformSDK: package path not found: %s", package_path)
            return 0

        for root, _, files in os.walk(package_path):
            for filename in files:
                if filename.endswith(".py") and not filename.startswith("_"):
                    module_path = os.path.join(root, filename)
                    try:
                        rel_path = os.path.relpath(module_path, os.path.dirname(package_path))
                        module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                        importlib.import_module(module_name)
                        discovered += 1
                    except Exception as e:
                        logger.error("PlatformSDK: failed to import %s: %s", module_path, e)

        logger.info("PlatformSDK: discovered %d modules in %s", discovered, package_path)
        return discovered

    def create_agent_instance(self, name: str, *args: Any, **kwargs: Any) -> Optional[Any]:
        """Create an instance of a registered agent class."""
        cls = self._agent_classes.get(name)
        if not cls:
            return None
        return cls(*args, **kwargs)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "registered_agents": len(self._agents),
            "registered_tools": len(self._tools),
            "registered_plugins": len(self._plugins),
            "agent_names": sorted(self._agents.keys()),
            "tool_names": sorted(self._tools.keys()),
        }
