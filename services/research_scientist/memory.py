"""Research Memory Engine - persistent knowledge repository for research."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class MemoryCategory(Enum):
    """Categories of research memory."""

    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    DISCOVERY = "discovery"
    BACKTEST = "backtest"
    VALIDATION = "validation"
    FAILURE = "failure"
    INSIGHT = "insight"
    STRATEGY = "strategy"


@dataclass
class ResearchMemoryEntry:
    """A single entry in the research knowledge base."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    category: MemoryCategory = MemoryCategory.HYPOTHESIS
    title: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    lesson: str = ""
    importance: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    related_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "category": self.category.value,
            "title": self.title, "content": self.content,
            "outcome": self.outcome, "lesson": self.lesson,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags, "related_ids": self.related_ids,
        }


class ResearchMemory:
    """Research Memory Engine.

    The AI Quant Brain - persistent knowledge repository that stores:
    - Hypotheses (proposed, tested, confirmed, rejected)
    - Experiments (designs, parameters, results)
    - Discoveries (factors, signals, patterns)
    - Backtests (performance, metrics, attribution)
    - Failures (what didn't work and why)
    - Insights (lessons learned, patterns observed)

    Forms the long-term memory of the AI Research Lab,
    enabling cumulative learning and preventing repeated mistakes.
    """

    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.entries: Dict[str, ResearchMemoryEntry] = {}
        self.insights: List[Dict[str, Any]] = []
        self.failure_log: List[Dict[str, Any]] = []
        self.knowledge_graph: Dict[str, List[str]] = {}

    def save(self, research: Dict[str, Any]) -> Dict[str, Any]:
        """Save a research item to memory. Main entry point."""
        return self.save_entry(research).to_dict()

    def save_entry(
        self,
        research: Dict[str, Any],
        category: Optional[MemoryCategory] = None,
    ) -> ResearchMemoryEntry:
        """Save a research finding to persistent memory."""
        if category is None:
            category = self._infer_category(research)

        entry = ResearchMemoryEntry(
            category=category,
            title=research.get("title", research.get("name", "Untitled")),
            content=research,
            outcome=research.get("outcome", research.get("status", "unknown")),
            lesson=self._extract_lesson(research, category),
            importance=self._assess_importance(research),
            tags=self._extract_tags(research, category),
            related_ids=self._find_related(research),
        )

        self.entries[entry.id] = entry
        self.history.append({"action": "saved", "entry_id": entry.id,
                             "category": category.value,
                             "timestamp": datetime.now(timezone.utc).isoformat()})

        # Track failures separately
        if category == MemoryCategory.FAILURE:
            self.failure_log.append({"entry_id": entry.id, "lesson": entry.lesson,
                                     "timestamp": entry.created_at.isoformat()})

        # Track insights
        if category == MemoryCategory.INSIGHT or entry.importance > 0.7:
            self.insights.append({"entry_id": entry.id, "title": entry.title,
                                  "lesson": entry.lesson, "importance": entry.importance})

        # Update knowledge graph
        self._update_knowledge_graph(entry)

        return entry

    def _infer_category(self, research: Dict[str, Any]) -> MemoryCategory:
        rtype = research.get("type", "").lower()
        mapping = {
            "hypothesis": MemoryCategory.HYPOTHESIS,
            "experiment": MemoryCategory.EXPERIMENT,
            "discovery": MemoryCategory.DISCOVERY,
            "backtest": MemoryCategory.BACKTEST,
            "validation": MemoryCategory.VALIDATION,
            "failure": MemoryCategory.FAILURE,
            "insight": MemoryCategory.INSIGHT,
            "strategy": MemoryCategory.STRATEGY,
        }
        return mapping.get(rtype, MemoryCategory.HYPOTHESIS)

    def _extract_lesson(self, research: Dict[str, Any], category: MemoryCategory) -> str:
        lessons = {
            MemoryCategory.HYPOTHESIS: f"Hypothesis tested: {research.get('statement', research.get('name', ''))}",
            MemoryCategory.EXPERIMENT: f"Experiment completed: {research.get('name', '')}",
            MemoryCategory.DISCOVERY: f"Discovered: {research.get('name', '')} with Sharpe {research.get('sharpe', 0)}",
            MemoryCategory.BACKTEST: f"Backtest result: Sharpe {research.get('sharpe_ratio', 0)}",
            MemoryCategory.VALIDATION: f"Validation: {research.get('status', 'completed')}",
            MemoryCategory.FAILURE: f"FAILED: {research.get('name', '')} - {research.get('reason', 'No reason recorded')}",
            MemoryCategory.INSIGHT: f"Insight: {research.get('description', '')}",
            MemoryCategory.STRATEGY: f"Strategy: {research.get('strategy_name', '')}",
        }
        return lessons.get(category, "Research record saved")

    def _assess_importance(self, research: Dict[str, Any]) -> float:
        sharpe = research.get("sharpe_ratio", research.get("sharpe", 0))
        importance = min(0.5 + abs(sharpe) * 0.3, 1.0)
        status = research.get("status", "")
        if status in ("confirmed", "published", "deployed"):
            importance = min(importance + 0.2, 1.0)
        elif status in ("rejected", "failed"):
            importance = max(importance - 0.1, 0.1)
        return round(importance, 2)

    def _extract_tags(self, research: Dict[str, Any], category: MemoryCategory) -> List[str]:
        tags = research.get("tags", [])
        tags.append(category.value)
        return list(set(tags))

    def _find_related(self, research: Dict[str, Any]) -> List[str]:
        related = []
        name = research.get("name", research.get("strategy_name", "")).lower()
        for eid, entry in self.entries.items():
            if name and name in entry.title.lower():
                related.append(eid)
        return related[:5]

    def _update_knowledge_graph(self, entry: ResearchMemoryEntry) -> None:
        for related_id in entry.related_ids:
            if entry.id not in self.knowledge_graph:
                self.knowledge_graph[entry.id] = []
            self.knowledge_graph[entry.id].append(related_id)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search the research memory."""
        results = []
        query_lower = query.lower()
        for entry in self.entries.values():
            if (query_lower in entry.title.lower() or
                query_lower in entry.lesson.lower() or
                any(query_lower in tag for tag in entry.tags)):
                results.append(entry.to_dict())
        return results

    def get_failures(self) -> List[Dict[str, Any]]:
        """Get all recorded failures for learning."""
        return self.failure_log

    def get_insights(self, min_importance: float = 0.0) -> List[Dict[str, Any]]:
        """Get high-value insights."""
        return [i for i in self.insights if i["importance"] >= min_importance]

    def get_by_category(self, category: MemoryCategory) -> List[Dict[str, Any]]:
        """Get all entries of a specific category."""
        return [e.to_dict() for e in self.entries.values() if e.category == category]

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive memory summary."""
        category_counts = {}
        for e in self.entries.values():
            cat = e.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        avg_importance = (sum(e.importance for e in self.entries.values()) /
                          max(len(self.entries), 1))

        return {
            "total_entries": len(self.entries),
            "by_category": category_counts,
            "total_failures": len(self.failure_log),
            "total_insights": len(self.insights),
            "avg_importance": round(avg_importance, 2),
            "knowledge_graph_nodes": len(self.knowledge_graph),
        }
