"""Tool Selector — intelligent tool selection with multi-criteria ranking.

Pipeline:
    DiscoveryResult (candidate tools)
        -> ToolSelector
        -> Scoring (relevance, performance, risk, permission)
        -> Ranking
        -> Best Tool(s)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_catalog import CatalogEntry
from services.ai_agent.tooling.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ── CandidateTool ──

@dataclass
class CandidateTool:
    """A tool candidate with selection scoring."""

    entry: CatalogEntry
    score: float = 0.0
    relevance_score: float = 0.0
    performance_score: float = 0.0
    risk_score: float = 0.0
    permission_score: float = 0.0
    rank: int = 0
    selection_reason: str = ""

    @property
    def tool_name(self) -> str:
        return self.entry.name


# ── SelectionResult ──

@dataclass
class SelectionResult:
    """Result of a tool selection operation."""

    candidates: List[CandidateTool] = field(default_factory=list)
    selected: Optional[CandidateTool] = None
    total_evaluated: int = 0
    elapsed_ms: float = 0.0

    @property
    def has_selection(self) -> bool:
        return self.selected is not None

    @property
    def best_match(self) -> Optional[CandidateTool]:
        if not self.candidates:
            return None
        return self.candidates[0]


# ── ToolSelector ──

class ToolSelector:
    """Intelligent tool selection engine with multi-criteria scoring.

    Ranks candidate tools based on relevance, historical performance,
    risk level, and permission compatibility. Selects the best tool
    for a given task.

    Supports:
        - Multi-criteria scoring (relevance, performance, risk, permission)
        - Weighted ranking
        - Top-N selection
        - Selection rationale

    Usage:
        selector = ToolSelector(registry)
        result = await selector.select(discovery_result, intent)
        best_tool = result.selected
    """

    # Default scoring weights
    DEFAULT_WEIGHTS: Dict[str, float] = {
        "relevance": 0.40,
        "performance": 0.30,
        "risk": 0.15,
        "permission": 0.15,
    }

    def __init__(
        self,
        registry: ToolRegistry,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialize the selector.

        Args:
            registry: The ToolRegistry for metadata lookup.
            weights: Optional custom scoring weights.
        """
        self._registry = registry
        self._weights = weights or self.DEFAULT_WEIGHTS
        self._initialized: bool = False
        logger.info("ToolSelector created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the selector."""
        self._initialized = True
        logger.info("ToolSelector initialized")

    async def shutdown(self) -> None:
        """Shutdown the selector."""
        self._initialized = False
        logger.info("ToolSelector shutdown complete")

    # ── Selection ──

    async def select(
        self,
        entries: List[CatalogEntry],
        intent: str = "",
        top_n: int = 1,
        granted_permissions: Optional[set] = None,
    ) -> SelectionResult:
        """Select the best tool(s) from a list of candidates.

        Args:
            entries: Candidate catalog entries from discovery.
            intent: The original task intent for relevance scoring.
            top_n: Number of top candidates to return.
            granted_permissions: Set of permissions the caller has.

        Returns:
            SelectionResult with ranked candidates.
        """
        import time

        start = time.monotonic()

        candidates: List[CandidateTool] = []
        for entry in entries:
            candidate = self._score_candidate(entry, intent, granted_permissions)
            candidates.append(candidate)

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Assign ranks
        for i, c in enumerate(candidates):
            c.rank = i + 1

        selected = candidates[0] if candidates else None
        elapsed = (time.monotonic() - start) * 1000

        logger.info(
            f"Tool selection: {len(candidates)} evaluated, "
            f"selected '{selected.tool_name}' (score={selected.score:.3f})"
            if selected
            else "Tool selection: no candidates"
        )

        return SelectionResult(
            candidates=candidates[:top_n],
            selected=selected,
            total_evaluated=len(candidates),
            elapsed_ms=elapsed,
        )

    async def select_best(
        self,
        entries: List[CatalogEntry],
        intent: str = "",
        granted_permissions: Optional[set] = None,
    ) -> Optional[CandidateTool]:
        """Select the single best tool.

        Args:
            entries: Candidate catalog entries.
            intent: The original task intent.
            granted_permissions: Set of permissions the caller has.

        Returns:
            The best CandidateTool, or None if no candidates.
        """
        result = await self.select(entries, intent, top_n=1, granted_permissions=granted_permissions)
        return result.selected

    # ── Scoring ──

    def _score_candidate(
        self,
        entry: CatalogEntry,
        intent: str,
        granted_permissions: Optional[set],
    ) -> CandidateTool:
        """Score a single candidate across all criteria.

        Args:
            entry: The catalog entry to score.
            intent: The original task intent.
            granted_permissions: Set of permissions the caller has.

        Returns:
            A CandidateTool with scores populated.
        """
        relevance = self._score_relevance(entry, intent)
        performance = self._score_performance(entry)
        risk = self._score_risk(entry)
        permission = self._score_permission(entry, granted_permissions)

        total = (
            relevance * self._weights["relevance"]
            + performance * self._weights["performance"]
            + risk * self._weights["risk"]
            + permission * self._weights["permission"]
        )

        reasons: List[str] = []
        if relevance > 0.7:
            reasons.append("high relevance")
        if performance > 0.7:
            reasons.append("strong performance")
        if risk > 0.8:
            reasons.append("low risk")
        if permission > 0.5:
            reasons.append("permission granted")

        return CandidateTool(
            entry=entry,
            score=round(total, 4),
            relevance_score=round(relevance, 4),
            performance_score=round(performance, 4),
            risk_score=round(risk, 4),
            permission_score=round(permission, 4),
            selection_reason="; ".join(reasons) if reasons else "default match",
        )

    def _score_relevance(self, entry: CatalogEntry, intent: str) -> float:
        """Score relevance of a tool to the intent.

        Args:
            entry: The catalog entry.
            intent: The task intent text.

        Returns:
            Relevance score (0.0 to 1.0).
        """
        if not intent:
            return 0.5
        intent_lower = intent.lower()
        name_lower = entry.name.lower()
        desc_lower = entry.description.lower()

        score = 0.0
        # Exact name match
        if intent_lower in name_lower or name_lower in intent_lower:
            score += 0.4
        # Description match
        intent_words = set(intent_lower.split())
        desc_words = set(desc_lower.split())
        common = intent_words & desc_words
        if desc_words:
            score += 0.3 * (len(common) / max(len(intent_words), 1))
        # Tag match
        tag_match = sum(1 for t in entry.tags if t.lower() in intent_lower)
        if tag_match > 0:
            score += 0.3 * min(tag_match / 3, 1.0)

        return min(score, 1.0)

    def _score_performance(self, entry: CatalogEntry) -> float:
        """Score based on historical performance.

        Args:
            entry: The catalog entry.

        Returns:
            Performance score (0.0 to 1.0).
        """
        meta = self._registry.get_metadata(entry.name)
        if meta is None or meta.total_calls == 0:
            return 0.5  # No data, neutral score
        return meta.success_rate

    def _score_risk(self, entry: CatalogEntry) -> float:
        """Score based on risk level (higher = lower risk).

        Args:
            entry: The catalog entry.

        Returns:
            Risk score (0.0 to 1.0), where 1.0 is safest.
        """
        risk_map = {
            "low": 1.0,
            "medium": 0.7,
            "high": 0.3,
            "critical": 0.0,
        }
        return risk_map.get(entry.tool.risk_level, 0.5)

    def _score_permission(
        self,
        entry: CatalogEntry,
        granted_permissions: Optional[set],
    ) -> float:
        """Score based on permission compatibility.

        Args:
            entry: The catalog entry.
            granted_permissions: Set of granted permissions.

        Returns:
            Permission score (0.0 or 1.0).
        """
        if granted_permissions is None:
            return 0.5  # Unknown permissions, neutral
        if entry.tool.permission in granted_permissions:
            return 1.0
        return 0.0  # Permission not granted

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get selector status."""
        return {
            "weights": self._weights,
            "initialized": self._initialized,
        }
