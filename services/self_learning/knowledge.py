"""Knowledge Memory Engine - stores and retrieves trading knowledge."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class KnowledgeType(Enum):
    """Type of stored knowledge."""
    MARKET = "MARKET"
    STRATEGY = "STRATEGY"
    LESSON = "LESSON"
    PATTERN = "PATTERN"
    DECISION = "DECISION"
    INSIGHT = "INSIGHT"
    RULE = "RULE"


class KnowledgeDomain(Enum):
    """Domain of knowledge."""
    MACRO = "MACRO"
    TECHNICAL = "TECHNICAL"
    FUNDAMENTAL = "FUNDAMENTAL"
    SENTIMENT = "SENTIMENT"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    PORTFOLIO = "PORTFOLIO"


class KnowledgePriority(Enum):
    """Priority level of knowledge."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge."""
    entry_id: str
    timestamp: float
    knowledge_type: KnowledgeType
    domain: KnowledgeDomain
    priority: KnowledgePriority
    title: str
    content: str
    source: str
    confidence: float
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)
    usage_count: int = 0
    validated: bool = False
    last_accessed: float = 0.0

    def access(self):
        self.usage_count += 1
        self.last_accessed = time.time()

    def relevance_score(self, query_tags: List[str]) -> float:
        tag_overlap = len(set(self.tags).intersection(set(query_tags)))
        tag_score = tag_overlap / max(len(query_tags), 1)
        return self.confidence * (0.5 + 0.5 * tag_score)


@dataclass
class KnowledgeGraph:
    """Graph representation of knowledge relationships."""
    entries: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)

    def add_entry(self, entry: KnowledgeEntry):
        self.entries[entry.entry_id] = entry

    def add_edge(self, from_id: str, to_id: str):
        if from_id not in self.edges:
            self.edges[from_id] = []
        self.edges[from_id].append(to_id)

    def get_related(self, entry_id: str, depth: int = 1) -> List[str]:
        result = set()
        current = [entry_id]
        for _ in range(depth):
            next_level = []
            for eid in current:
                neighbors = self.edges.get(eid, [])
                for n in neighbors:
                    if n not in result:
                        result.add(n)
                        next_level.append(n)
            current = next_level
        return list(result)


class KnowledgeMemoryEngine:
    """Knowledge Memory Engine.

    Stores and organizes:
    - Market Knowledge
    - Trading Lessons
    - Strategy Experience
    - Decision History

    Forms the "AI Trading Brain" - institutional knowledge that
    persists across trading sessions and improves over time.
    """

    def __init__(self):
        self.memory: List[KnowledgeEntry] = []
        self.graph = KnowledgeGraph()
        self._entry_counter = 0

    def store(self, knowledge: Dict[str, Any]) -> Dict[str, Any]:
        """Store a piece of knowledge.

        Args:
            knowledge: Knowledge data dict.

        Returns:
            Dict with storage confirmation.
        """
        entry = KnowledgeEntry(
            entry_id=f"KN_{self._entry_counter:06d}",
            timestamp=knowledge.get("timestamp", time.time()),
            knowledge_type=KnowledgeType(knowledge.get("type", "INSIGHT")),
            domain=KnowledgeDomain(knowledge.get("domain", "MARKET")),
            priority=KnowledgePriority(knowledge.get("priority", "MEDIUM")),
            title=knowledge.get("title", ""),
            content=knowledge.get("content", ""),
            source=knowledge.get("source", "unknown"),
            confidence=knowledge.get("confidence", 0.5),
            tags=knowledge.get("tags", []),
            related_entries=knowledge.get("related", []),
        )

        self.memory.append(entry)
        self.graph.add_entry(entry)
        self._entry_counter += 1

        # Link related entries
        for related_id in entry.related_entries:
            if related_id in self.graph.entries:
                self.graph.add_edge(entry.entry_id, related_id)

        return {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "type": entry.knowledge_type.value,
            "domain": entry.domain.value,
            "priority": entry.priority.value,
            "memory_size": len(self.memory),
        }

    def query(self, filters: Dict[str, Any] = None) -> List[KnowledgeEntry]:
        """Query knowledge memory with filters.

        Args:
            filters: Optional dict of filter criteria.

        Returns:
            Filtered list of knowledge entries.
        """
        results = self.memory
        if filters is None:
            return results

        if "type" in filters:
            results = [e for e in results
                       if e.knowledge_type.value == filters["type"]]
        if "domain" in filters:
            results = [e for e in results
                       if e.domain.value == filters["domain"]]
        if "priority" in filters:
            results = [e for e in results
                       if e.priority.value == filters["priority"]]
        if "min_confidence" in filters:
            results = [e for e in results
                       if e.confidence >= filters["min_confidence"]]
        if "validated_only" in filters and filters["validated_only"]:
            results = [e for e in results if e.validated]
        if "tags" in filters:
            tag_set = set(filters["tags"])
            results = [e for e in results
                       if tag_set.intersection(set(e.tags))]
        if "source" in filters:
            results = [e for e in results
                       if e.source == filters["source"]]

        # Mark accessed
        for e in results:
            e.access()

        return results

    def search(self, query_text: str, top_k: int = 10) -> List[KnowledgeEntry]:
        """Semantic-like search over knowledge memory.

        Args:
            query_text: Search query string.
            top_k: Maximum results to return.

        Returns:
            Top-k matching knowledge entries.
        """
        query_lower = query_text.lower()
        scored = []

        for entry in self.memory:
            score = 0.0
            if query_lower in entry.title.lower():
                score += 3.0
            if query_lower in entry.content.lower():
                score += 2.0
            if query_lower in " ".join(entry.tags).lower():
                score += 1.5
            if query_lower in entry.domain.value.lower():
                score += 1.0
            score *= entry.confidence
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [e for e, _ in scored[:top_k]]
        for e in results:
            e.access()
        return results

    def get_lessons(self, domain: str = None,
                    min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """Get all stored lessons.

        Args:
            domain: Optional domain filter.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of lesson dicts.
        """
        lessons = [e for e in self.memory
                   if e.knowledge_type == KnowledgeType.LESSON
                   and e.confidence >= min_confidence]

        if domain:
            lessons = [e for e in lessons
                       if e.domain.value == domain]

        for e in lessons:
            e.access()

        return [
            {
                "id": e.entry_id,
                "title": e.title,
                "content": e.content,
                "domain": e.domain.value,
                "priority": e.priority.value,
                "confidence": e.confidence,
                "validated": e.validated,
                "tags": e.tags,
            }
            for e in lessons
        ]

    def validate_knowledge(self, entry_id: str) -> Dict[str, Any]:
        """Validate a piece of knowledge.

        Args:
            entry_id: Knowledge entry ID to validate.

        Returns:
            Dict with validation result.
        """
        for entry in self.memory:
            if entry.entry_id == entry_id:
                entry.validated = True
                return {
                    "entry_id": entry_id,
                    "validated": True,
                    "title": entry.title,
                }
        return {"entry_id": entry_id, "validated": False, "error": "Not found"}

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge memory statistics.

        Returns:
            Dict with statistics.
        """
        if not self.memory:
            return {"total_entries": 0}

        by_type = {}
        by_domain = {}
        by_priority = {}
        for e in self.memory:
            by_type[e.knowledge_type.value] = by_type.get(e.knowledge_type.value, 0) + 1
            by_domain[e.domain.value] = by_domain.get(e.domain.value, 0) + 1
            by_priority[e.priority.value] = by_priority.get(e.priority.value, 0) + 1

        return {
            "total_entries": len(self.memory),
            "validated": sum(1 for e in self.memory if e.validated),
            "by_type": by_type,
            "by_domain": by_domain,
            "by_priority": by_priority,
            "avg_confidence": sum(e.confidence for e in self.memory) / len(self.memory),
            "most_accessed": sorted(self.memory, key=lambda e: e.usage_count, reverse=True)[:5],
        }

    def export_rules(self) -> List[Dict[str, Any]]:
        """Export knowledge as actionable rules.

        Returns:
            List of rule dicts.
        """
        rules = []
        for e in self.memory:
            if e.knowledge_type == KnowledgeType.RULE and e.validated:
                rules.append({
                    "rule_id": e.entry_id,
                    "title": e.title,
                    "condition": e.content,
                    "domain": e.domain.value,
                    "priority": e.priority.value,
                    "confidence": e.confidence,
                    "tags": e.tags,
                })
        return sorted(rules, key=lambda r: r["confidence"], reverse=True)
