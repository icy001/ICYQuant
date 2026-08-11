"""Tool Registry — unified tool registration, lookup, and lifecycle management.

Pipeline:
    ToolDefinition
        -> register()
        -> Registry (in-memory + persistence)
        -> lookup() / list_by_category() / list_by_capability()
        -> Discovery / Selector / Router
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from services.ai_agent.tooling.tool_definition import ToolDefinition
from services.ai_agent.tooling.tool_metadata import ToolMetadata

logger = logging.getLogger(__name__)


# ── ToolRegistry ──

class ToolRegistry:
    """Central registry for all tools available to AI Agents.

    Maintains tool definitions and their runtime metadata. Supports
    registration, unregistration, lookup, and capability-based discovery.

    Supports:
        - Tool registration / unregistration
        - Name-based and ID-based lookup
        - Category and capability filtering
        - Version tracking
        - Permission-aware listing
        - Metadata attachment

    Usage:
        registry = ToolRegistry()
        await registry.initialize()
        registry.register(tool_definition)
        tool = registry.lookup("backtest.run")
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: Dict[str, ToolDefinition] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._initialized: bool = False
        logger.info("ToolRegistry created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the registry and load persisted tools."""
        self._initialized = True
        logger.info("ToolRegistry initialized")

    async def shutdown(self) -> None:
        """Shutdown the registry and persist state."""
        self._tools.clear()
        self._metadata.clear()
        self._initialized = False
        logger.info("ToolRegistry shutdown complete")

    # ── Registration ──

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition.

        Args:
            tool: The tool definition to register.

        Raises:
            ValueError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        self._tools[tool.tool_id] = tool
        self._metadata[tool.name] = ToolMetadata(tool_name=tool.name)
        logger.info(f"Tool registered: {tool.name} (id={tool.tool_id})")

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool by name.

        Args:
            tool_name: The name of the tool to unregister.

        Raises:
            KeyError: If the tool is not found.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool not found: {tool_name}")
        tool = self._tools[tool_name]
        self._tools.pop(tool_name, None)
        self._tools.pop(tool.tool_id, None)
        self._metadata.pop(tool_name, None)
        logger.info(f"Tool unregistered: {tool_name}")

    def update(self, tool: ToolDefinition) -> None:
        """Update an existing tool definition.

        Args:
            tool: The updated tool definition.

        Raises:
            KeyError: If the tool is not found.
        """
        if tool.name not in self._tools:
            raise KeyError(f"Tool not found for update: {tool.name}")
        old = self._tools[tool.name]
        self._tools.pop(old.tool_id, None)
        self._tools[tool.name] = tool
        self._tools[tool.tool_id] = tool
        logger.info(f"Tool updated: {tool.name}")

    # ── Lookup ──

    def lookup(self, identifier: str) -> Optional[ToolDefinition]:
        """Look up a tool by name or ID.

        Args:
            identifier: Tool name or tool_id.

        Returns:
            The tool definition, or None if not found.
        """
        return self._tools.get(identifier)

    def get(self, tool_name: str) -> ToolDefinition:
        """Get a tool by name, raising if not found.

        Args:
            tool_name: The tool name.

        Returns:
            The tool definition.

        Raises:
            KeyError: If the tool is not found.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool not found: {tool_name}")
        return self._tools[tool_name]

    def get_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """Get runtime metadata for a tool.

        Args:
            tool_name: The tool name.

        Returns:
            The tool metadata, or None if not found.
        """
        return self._metadata.get(tool_name)

    # ── Listing ──

    def list_all(self, include_deprecated: bool = False) -> List[ToolDefinition]:
        """List all registered tools.

        Args:
            include_deprecated: Whether to include deprecated tools.

        Returns:
            List of tool definitions.
        """
        seen: Set[str] = set()
        tools: List[ToolDefinition] = []
        for tool in self._tools.values():
            if tool.name in seen:
                continue
            seen.add(tool.name)
            if not include_deprecated and tool.deprecated:
                continue
            tools.append(tool)
        return tools

    def list_by_category(self, category: str) -> List[ToolDefinition]:
        """List tools in a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of matching tool definitions.
        """
        return [t for t in self.list_all() if t.category == category]

    def list_by_capability(self, capability: str) -> List[ToolDefinition]:
        """List tools with a specific capability.

        Args:
            capability: The capability to filter by.

        Returns:
            List of matching tool definitions.
        """
        return [t for t in self.list_all() if t.capability == capability]

    def list_by_tag(self, tag: str) -> List[ToolDefinition]:
        """List tools with a specific tag.

        Args:
            tag: The tag to filter by.

        Returns:
            List of matching tool definitions.
        """
        return [t for t in self.list_all() if tag in t.tags]

    def list_by_permission(self, permission: str) -> List[ToolDefinition]:
        """List tools requiring a specific permission.

        Args:
            permission: The permission to filter by.

        Returns:
            List of matching tool definitions.
        """
        return [t for t in self.list_all() if t.permission == permission]

    def list_accessible(self, granted_permissions: Set[str]) -> List[ToolDefinition]:
        """List tools accessible with a set of granted permissions.

        Args:
            granted_permissions: The set of permissions the caller has.

        Returns:
            List of accessible tool definitions.
        """
        return [t for t in self.list_all() if t.permission in granted_permissions]

    # ── Status ──

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self.list_all(include_deprecated=True))

    @property
    def active_count(self) -> int:
        """Number of active (non-deprecated) tools."""
        return len(self.list_all(include_deprecated=False))

    @property
    def categories(self) -> List[str]:
        """All unique categories."""
        return sorted({t.category for t in self.list_all(include_deprecated=True)})

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the registry state."""
        return {
            "total_tools": self.count,
            "active_tools": self.active_count,
            "categories": self.categories,
            "tools": {
                name: {
                    "version": meta.tool_name,
                    "health": self._metadata[name].health_status if name in self._metadata else "unknown",
                    "total_calls": self._metadata[name].total_calls if name in self._metadata else 0,
                }
                for name, meta in self._metadata.items()
            },
        }
