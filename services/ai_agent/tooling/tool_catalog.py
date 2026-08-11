"""Tool Catalog — structured tool inventory with multi-index search.

Data flow:
    ToolRegistry
        -> ToolCatalog (indexed views)
        -> Name Index / Category Index / Tag Index / Capability Index
        -> Search / Filter
        -> ToolDiscovery / ToolSelector
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


# ── CatalogEntry ──

@dataclass
class CatalogEntry:
    """A catalog entry wrapping a tool definition with search metadata."""

    tool: ToolDefinition
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def name(self) -> str:
        return self.tool.name

    @property
    def description(self) -> str:
        return self.tool.description

    @property
    def category(self) -> str:
        return self.tool.category

    @property
    def tags(self) -> List[str]:
        return self.tool.tags

    @property
    def capability(self) -> str:
        return self.tool.capability

    def to_dict(self) -> Dict[str, Any]:
        """Serialize catalog entry to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "capability": self.capability,
            "version": self.tool.version,
            "permission": self.tool.permission,
            "risk_level": self.tool.risk_level,
            "is_idempotent": self.tool.is_idempotent,
            "is_streaming": self.tool.is_streaming,
            "deprecated": self.tool.deprecated,
            "indexed_at": self.indexed_at.isoformat(),
        }


# ── ToolCatalog ──

class ToolCatalog:
    """Structured, multi-index catalog of all registered tools.

    Provides fast lookup across multiple dimensions: name, category,
    tag, and capability. Used by ToolDiscovery and ToolSelector for
    efficient tool search and ranking.

    Supports:
        - Multi-index (name, category, tag, capability)
        - Full-text search over name + description
        - Filtered listing
        - Dynamic re-indexing on registry change

    Usage:
        catalog = ToolCatalog()
        catalog.index_tools(registry.list_all())
        results = catalog.search("backtest")
    """

    def __init__(self) -> None:
        """Initialize an empty catalog."""
        self._entries: Dict[str, CatalogEntry] = {}

        # ── Indexes ──
        self._by_name: Dict[str, CatalogEntry] = {}
        self._by_category: Dict[str, List[CatalogEntry]] = {}
        self._by_tag: Dict[str, List[CatalogEntry]] = {}
        self._by_capability: Dict[str, List[CatalogEntry]] = {}

        self._initialized: bool = False
        logger.info("ToolCatalog created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the catalog."""
        self._initialized = True
        logger.info("ToolCatalog initialized")

    async def shutdown(self) -> None:
        """Shutdown the catalog."""
        self._entries.clear()
        self._by_name.clear()
        self._by_category.clear()
        self._by_tag.clear()
        self._by_capability.clear()
        self._initialized = False
        logger.info("ToolCatalog shutdown complete")

    # ── Indexing ──

    def index_tools(self, tools: List[ToolDefinition]) -> None:
        """Index a list of tool definitions.

        Args:
            tools: The tools to index.
        """
        for tool in tools:
            self.index_tool(tool)
        logger.info(f"Catalog indexed {len(tools)} tools")

    def index_tool(self, tool: ToolDefinition) -> None:
        """Index a single tool definition.

        Args:
            tool: The tool to index.
        """
        entry = CatalogEntry(tool=tool)
        self._entries[tool.name] = entry

        # Name index
        self._by_name[tool.name] = entry

        # Category index
        cat = tool.category or "uncategorized"
        if cat not in self._by_category:
            self._by_category[cat] = []
        self._by_category[cat].append(entry)

        # Tag index
        for tag in tool.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            self._by_tag[tag].append(entry)

        # Capability index
        cap = tool.capability or "none"
        if cap not in self._by_capability:
            self._by_capability[cap] = []
        self._by_capability[cap].append(entry)

    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from all indexes.

        Args:
            tool_name: The name of the tool to remove.
        """
        entry = self._entries.pop(tool_name, None)
        if entry is None:
            return
        self._by_name.pop(tool_name, None)

        cat = entry.tool.category or "uncategorized"
        if cat in self._by_category:
            self._by_category[cat] = [e for e in self._by_category[cat] if e.name != tool_name]

        for tag in entry.tool.tags:
            if tag in self._by_tag:
                self._by_tag[tag] = [e for e in self._by_tag[tag] if e.name != tool_name]

        cap = entry.tool.capability or "none"
        if cap in self._by_capability:
            self._by_capability[cap] = [e for e in self._by_capability[cap] if e.name != tool_name]

    # ── Search ──

    def search(
        self,
        query: str = "",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capability: Optional[str] = None,
        include_deprecated: bool = False,
        limit: int = 20,
    ) -> List[CatalogEntry]:
        """Search the catalog with multiple filter dimensions.

        Args:
            query: Free-text search over name and description.
            category: Filter by category.
            tags: Filter by tags (any match).
            capability: Filter by capability.
            include_deprecated: Whether to include deprecated tools.
            limit: Maximum number of results.

        Returns:
            List of matching catalog entries.
        """
        candidates: List[CatalogEntry] = list(self._entries.values())

        # Filter deprecated
        if not include_deprecated:
            candidates = [e for e in candidates if not e.tool.deprecated]

        # Filter by category
        if category:
            candidates = [e for e in candidates if e.tool.category == category]

        # Filter by tags
        if tags:
            candidates = [e for e in candidates if any(t in e.tool.tags for t in tags)]

        # Filter by capability
        if capability:
            candidates = [e for e in candidates if e.tool.capability == capability]

        # Text search
        if query:
            q = query.lower()
            candidates = [
                e
                for e in candidates
                if q in e.tool.name.lower() or q in e.tool.description.lower()
            ]

        return candidates[:limit]

    # ── Indexed Lookups ──

    def get_by_name(self, name: str) -> Optional[CatalogEntry]:
        """Get a catalog entry by tool name."""
        return self._by_name.get(name)

    def get_by_category(self, category: str) -> List[CatalogEntry]:
        """Get all entries in a category."""
        return self._by_category.get(category, [])

    def get_by_tag(self, tag: str) -> List[CatalogEntry]:
        """Get all entries with a specific tag."""
        return self._by_tag.get(tag, [])

    def get_by_capability(self, capability: str) -> List[CatalogEntry]:
        """Get all entries with a specific capability."""
        return self._by_capability.get(capability, [])

    # ── Status ──

    @property
    def entry_count(self) -> int:
        """Total number of indexed entries."""
        return len(self._entries)

    @property
    def category_count(self) -> int:
        """Number of unique categories."""
        return len(self._by_category)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the catalog state."""
        return {
            "total_entries": self.entry_count,
            "categories": list(self._by_category.keys()),
            "tags": list(self._by_tag.keys()),
            "capabilities": list(self._by_capability.keys()),
            "category_counts": {k: len(v) for k, v in self._by_category.items()},
            "tag_counts": {k: len(v) for k, v in self._by_tag.items()},
        }
