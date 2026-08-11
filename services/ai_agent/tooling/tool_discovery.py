"""Tool Discovery — automatic tool finding for AI Agent tasks.

Pipeline:
    Task Intent
        -> ToolDiscovery
        -> Keyword Search / Capability Match / Semantic Search / Tag Search
        -> Candidate Tools
        -> ToolSelector
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_catalog import CatalogEntry, ToolCatalog

logger = logging.getLogger(__name__)


# ── DiscoveryResult ──

@dataclass
class DiscoveryResult:
    """Result of a tool discovery operation."""

    query: str
    entries: List[CatalogEntry] = field(default_factory=list)
    total_found: int = 0
    strategy_used: str = ""
    elapsed_ms: float = 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


# ── ToolDiscovery ──

class ToolDiscovery:
    """Discovers available tools matching a given task or intent.

    Uses the ToolCatalog to search across multiple dimensions:
    keyword matching, capability matching, semantic intent matching,
    and tag-based filtering.

    Supports:
        - Keyword search over name + description
        - Capability-based matching
        - Intent-based semantic discovery
        - Tag filtering
        - Result ranking

    Usage:
        discovery = ToolDiscovery(catalog)
        result = await discovery.discover("run a backtest")
    """

    def __init__(self, catalog: ToolCatalog) -> None:
        """Initialize with a tool catalog.

        Args:
            catalog: The ToolCatalog to search against.
        """
        self._catalog = catalog
        self._initialized: bool = False
        logger.info("ToolDiscovery created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the discovery engine."""
        self._initialized = True
        logger.info("ToolDiscovery initialized")

    async def shutdown(self) -> None:
        """Shutdown the discovery engine."""
        self._initialized = False
        logger.info("ToolDiscovery shutdown complete")

    # ── Discovery Methods ──

    async def discover(
        self,
        intent: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capability: Optional[str] = None,
        limit: int = 20,
    ) -> DiscoveryResult:
        """Discover tools matching the given intent.

        Args:
            intent: Natural language description of the task.
            category: Optional category filter.
            tags: Optional tag filters.
            capability: Optional capability filter.
            limit: Maximum results.

        Returns:
            DiscoveryResult with matching catalog entries.
        """
        import time

        start = time.monotonic()

        # ── Strategy 1: Keyword search ──
        entries = self._catalog.search(
            query=intent,
            category=category,
            tags=tags,
            capability=capability,
            limit=limit,
        )

        strategy = "keyword"
        if not entries:
            # ── Strategy 2: Broad capability match ──
            entries = self._discover_by_capability(intent, limit=limit)
            strategy = "capability"

        if not entries:
            # ── Strategy 3: Tag-based fallback ──
            entries = self._discover_by_tags(intent, limit=limit)
            strategy = "tag"

        elapsed = (time.monotonic() - start) * 1000

        logger.info(
            f"Discovery for '{intent[:50]}...': {len(entries)} results "
            f"using {strategy} strategy ({elapsed:.1f}ms)"
        )

        return DiscoveryResult(
            query=intent,
            entries=entries,
            total_found=len(entries),
            strategy_used=strategy,
            elapsed_ms=elapsed,
        )

    async def discover_by_capability(self, capability: str, limit: int = 20) -> DiscoveryResult:
        """Discover tools by capability name.

        Args:
            capability: The capability to match.
            limit: Maximum results.

        Returns:
            DiscoveryResult with matching entries.
        """
        import time

        start = time.monotonic()
        entries = self._catalog.search(capability=capability, limit=limit)
        elapsed = (time.monotonic() - start) * 1000

        return DiscoveryResult(
            query=f"capability:{capability}",
            entries=entries,
            total_found=len(entries),
            strategy_used="capability",
            elapsed_ms=elapsed,
        )

    async def discover_by_category(self, category: str, limit: int = 20) -> DiscoveryResult:
        """Discover tools by category.

        Args:
            category: The category to match.
            limit: Maximum results.

        Returns:
            DiscoveryResult with matching entries.
        """
        import time

        start = time.monotonic()
        entries = self._catalog.search(category=category, limit=limit)
        elapsed = (time.monotonic() - start) * 1000

        return DiscoveryResult(
            query=f"category:{category}",
            entries=entries,
            total_found=len(entries),
            strategy_used="category",
            elapsed_ms=elapsed,
        )

    async def discover_by_tag(self, tags: List[str], limit: int = 20) -> DiscoveryResult:
        """Discover tools by tags.

        Args:
            tags: The tags to match (any match).
            limit: Maximum results.

        Returns:
            DiscoveryResult with matching entries.
        """
        import time

        start = time.monotonic()
        entries = self._catalog.search(tags=tags, limit=limit)
        elapsed = (time.monotonic() - start) * 1000

        return DiscoveryResult(
            query=f"tags:{','.join(tags)}",
            entries=entries,
            total_found=len(entries),
            strategy_used="tag",
            elapsed_ms=elapsed,
        )

    # ── Private Methods ──

    def _discover_by_capability(self, intent: str, limit: int) -> List[CatalogEntry]:
        """Attempt capability-based discovery from intent text."""
        intent_lower = intent.lower()
        capability_keywords: Dict[str, List[str]] = {
            "backtest": ["backtest", "回测"],
            "research": ["research", "research", "研究", "分析"],
            "market_data": ["market", "price", "quote", "行情", "价格"],
            "order": ["order", "trade", "下单", "交易"],
            "risk": ["risk", "风险"],
            "strategy": ["strategy", "策略"],
            "portfolio": ["portfolio", "组合", "持仓"],
            "scheduler": ["schedule", "cron", "定时"],
        }
        for cap, kws in capability_keywords.items():
            if any(kw in intent_lower for kw in kws):
                return self._catalog.search(capability=cap, limit=limit)
        return []

    def _discover_by_tags(self, intent: str, limit: int) -> List[CatalogEntry]:
        """Attempt tag-based discovery from intent text."""
        intent_lower = intent.lower()
        tag_keywords: Dict[str, List[str]] = {
            "backtest": ["backtest", "回测"],
            "data": ["data", "数据"],
            "analysis": ["analysis", "分析"],
            "trading": ["trade", "交易"],
            "risk": ["risk", "风险"],
            "strategy": ["strategy", "策略"],
            "portfolio": ["portfolio", "组合"],
            "async": ["async", "异步"],
            "batch": ["batch", "批量"],
        }
        matching_tags: List[str] = []
        for tag, kws in tag_keywords.items():
            if any(kw in intent_lower for kw in kws):
                matching_tags.append(tag)
        if matching_tags:
            return self._catalog.search(tags=matching_tags, limit=limit)
        return []

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get discovery engine status."""
        return {
            "catalog_entries": self._catalog.entry_count,
            "categories": self._catalog.category_count,
            "initialized": self._initialized,
        }
