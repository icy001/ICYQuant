"""Blackboard System — shared knowledge board for collaborative reasoning and decision making.

Pipeline:
    Agent publishes observation
        -> Blackboard.post() (create entry with type + data)
        -> Blackboard (knowledge repository)
        -> other agents read / subscribe to changes
        -> Blackboard.reason() (collaborative inference)
        -> Blackboard.decide() (final decision)

The Blackboard serves as a shared workspace where agents can post observations,
read others' findings, and collaboratively reason toward a decision. This avoids
redundant computation and enables cumulative knowledge building.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class EntryType(str, Enum):
    """Types of blackboard entries."""
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    DECISION = "decision"
    QUESTION = "question"
    ANSWER = "answer"
    NOTE = "note"


class EntryConfidence(str, Enum):
    """Confidence levels for blackboard entries."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class BlackboardEntry:
    """An entry on the shared blackboard.

    Attributes:
        entry_id: Unique entry identifier.
        entry_type: Type of entry.
        title: Short title for the entry.
        content: The entry content/data.
        author_agent_id: Agent that posted this entry.
        confidence: Confidence level.
        tags: Searchable tags.
        references: IDs of referenced entries.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    entry_id: str = field(default_factory=lambda: uuid4().hex)
    entry_type: EntryType = EntryType.OBSERVATION
    title: str = ""
    content: Any = None
    author_agent_id: str = ""
    confidence: EntryConfidence = EntryConfidence.MEDIUM
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Return entry metadata as a dictionary."""
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "title": self.title,
            "author_agent_id": self.author_agent_id,
            "confidence": self.confidence.value,
            "tags": self.tags,
            "references": self.references,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BlackboardQuery:
    """Query parameters for searching the blackboard.

    Attributes:
        entry_type: Filter by entry type.
        author_agent_id: Filter by author agent.
        confidence: Minimum confidence level.
        tags: Filter by tags (AND match).
        keyword: Free-text keyword search.
        limit: Maximum results.
    """

    entry_type: Optional[EntryType] = None
    author_agent_id: Optional[str] = None
    confidence: Optional[EntryConfidence] = None
    tags: List[str] = field(default_factory=list)
    keyword: Optional[str] = None
    limit: int = 50


class Blackboard:
    """Shared knowledge board for collaborative agent reasoning.

    Agents post observations, hypotheses, findings, and recommendations.
    Other agents read and build upon them, enabling cumulative reasoning
    toward a final decision.

    Supports:
        - Post entries (observation, hypothesis, finding, recommendation, decision)
        - Read entries with filtering
        - Keyword and tag-based search
        - Reference tracking (entries that build on others)
        - Confidence scoring
        - Threaded reasoning chains
        - Change subscription

    Usage:
        blackboard = Blackboard(shared_memory)
        await blackboard.initialize()
        entry = await blackboard.post(
            entry_type=EntryType.OBSERVATION,
            title="Market volatility spike",
            content={"vix": 28.5},
            author_agent_id="market_agent",
        )
        results = blackboard.query(BlackboardQuery(entry_type=EntryType.OBSERVATION))
    """

    def __init__(self, shared_memory: SharedMemory, max_entries: int = 500) -> None:
        """Initialize the blackboard.

        Args:
            shared_memory: Shared memory for persistence.
            max_entries: Maximum number of entries.
        """
        self._shared_memory: SharedMemory = shared_memory
        self._max_entries: int = max_entries
        self._entries: Dict[str, BlackboardEntry] = {}
        self._subscriptions: Dict[str, List[Callable[[BlackboardEntry], Any]]] = {}
        self._initialized: bool = False
        logger.info("Blackboard created (max_entries=%d)", max_entries)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the blackboard."""
        if self._initialized:
            logger.warning("Blackboard already initialized")
            return
        self._initialized = True
        logger.info("Blackboard initialized")

    async def shutdown(self) -> None:
        """Shut down and clear the blackboard."""
        if not self._initialized:
            return
        self._entries.clear()
        self._subscriptions.clear()
        self._initialized = False
        logger.info("Blackboard shutdown complete")

    # ── Post ──

    async def post(
        self,
        entry_type: EntryType,
        title: str,
        content: Any,
        author_agent_id: str,
        confidence: EntryConfidence = EntryConfidence.MEDIUM,
        tags: Optional[List[str]] = None,
        references: Optional[List[str]] = None,
    ) -> BlackboardEntry:
        """Post a new entry to the blackboard.

        Args:
            entry_type: Type of entry.
            title: Short title.
            content: The entry content.
            author_agent_id: Posting agent's ID.
            confidence: Confidence level.
            tags: Searchable tags.
            references: Referenced entry IDs.

        Returns:
            The created blackboard entry.
        """
        if not self._initialized:
            raise RuntimeError("Blackboard not initialized")

        # Enforce max entries
        if len(self._entries) >= self._max_entries:
            self._evict_oldest()

        entry = BlackboardEntry(
            entry_type=entry_type,
            title=title,
            content=content,
            author_agent_id=author_agent_id,
            confidence=confidence,
            tags=tags or [],
            references=references or [],
        )
        self._entries[entry.entry_id] = entry

        # Persist to shared memory
        await self._shared_memory.write(
            key=f"blackboard:{entry.entry_id}",
            data={"type": entry_type.value, "title": title, "content": content},
            namespace="blackboard",
            owner_agent_id=author_agent_id,
            tags=tags,
        )

        # Notify subscribers
        await self._notify_subscribers(entry)

        logger.debug("Blackboard entry posted: %s (type=%s, by=%s)",
                     entry.entry_id, entry_type.value, author_agent_id)
        return entry

    # ── Read ──

    def get(self, entry_id: str) -> Optional[BlackboardEntry]:
        """Get an entry by ID.

        Args:
            entry_id: The entry identifier.

        Returns:
            The entry, or None if not found.
        """
        return self._entries.get(entry_id)

    def query(self, query: BlackboardQuery) -> List[BlackboardEntry]:
        """Search blackboard entries.

        Args:
            query: Search parameters.

        Returns:
            List of matching entries (most recent first).
        """
        results: List[BlackboardEntry] = []

        for entry in self._entries.values():
            if query.entry_type is not None and entry.entry_type != query.entry_type:
                continue
            if query.author_agent_id is not None and entry.author_agent_id != query.author_agent_id:
                continue
            if query.confidence is not None and entry.confidence != query.confidence:
                continue
            if query.tags:
                if not all(t in entry.tags for t in query.tags):
                    continue
            if query.keyword:
                keyword_lower = query.keyword.lower()
                searchable = f"{entry.title} {entry.entry_type.value} {' '.join(entry.tags)}"
                if keyword_lower not in searchable.lower():
                    continue
            results.append(entry)

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:query.limit]

    # ── Reasoning ──

    def get_reasoning_chain(self, entry_id: str) -> List[BlackboardEntry]:
        """Follow the reference chain backward from an entry.

        Args:
            entry_id: Starting entry ID.

        Returns:
            Ordered list of entries forming the reasoning chain.
        """
        chain: List[BlackboardEntry] = []
        visited: set = set()
        current_id = entry_id

        while current_id and current_id not in visited:
            entry = self._entries.get(current_id)
            if not entry:
                break
            visited.add(current_id)
            chain.append(entry)
            current_id = entry.references[0] if entry.references else ""

        chain.reverse()
        return chain

    def get_recommendations(self) -> List[BlackboardEntry]:
        """Get all recommendation entries.

        Returns:
            List of recommendation entries sorted by confidence.
        """
        confidence_order = {
            EntryConfidence.HIGH: 0,
            EntryConfidence.MEDIUM: 1,
            EntryConfidence.LOW: 2,
            EntryConfidence.UNKNOWN: 3,
        }
        recs = self.query(BlackboardQuery(entry_type=EntryType.RECOMMENDATION))
        recs.sort(key=lambda e: confidence_order.get(e.confidence, 99))
        return recs

    def get_decisions(self) -> List[BlackboardEntry]:
        """Get all decision entries.

        Returns:
            List of decision entries (most recent first).
        """
        return self.query(BlackboardQuery(entry_type=EntryType.DECISION))

    # ── Subscribe ──

    def subscribe(self, pattern: str, callback: Callable[[BlackboardEntry], Any]) -> str:
        """Subscribe to blackboard changes matching a pattern.

        Args:
            pattern: Regex pattern to match entry types or tags.
            callback: Function called with matching entries.

        Returns:
            Subscription ID for unsubscription.
        """
        sub_id = uuid4().hex[:8]
        self._subscriptions.setdefault(pattern, []).append(callback)
        logger.debug("Blackboard subscription added: %s", sub_id)
        return sub_id

    async def _notify_subscribers(self, entry: BlackboardEntry) -> None:
        """Notify matching subscribers of a new entry.

        Args:
            entry: The new entry.
        """
        for pattern, callbacks in self._subscriptions.items():
            try:
                compiled = re.compile(pattern)
                searchable = f"{entry.entry_type.value} {' '.join(entry.tags)}"
                if compiled.search(searchable):
                    for cb in callbacks:
                        try:
                            cb(entry)
                        except Exception:
                            logger.exception("Blackboard subscriber callback failed")
            except re.error:
                continue

    # ── Helpers ──

    def _evict_oldest(self) -> None:
        """Evict the oldest entry to make room."""
        if not self._entries:
            return
        oldest_id = min(
            self._entries.keys(),
            key=lambda k: self._entries[k].created_at,
        )
        del self._entries[oldest_id]
        logger.debug("Evicted oldest blackboard entry: %s", oldest_id)

    # ── Properties ──

    @property
    def count(self) -> int:
        """Return the number of entries."""
        return len(self._entries)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the blackboard state.

        Returns:
            Dict with entry count and type breakdown.
        """
        type_counts: Dict[str, int] = {}
        for e in self._entries.values():
            type_counts[e.entry_type.value] = type_counts.get(e.entry_type.value, 0) + 1

        return {
            "initialized": self._initialized,
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
            "type_breakdown": type_counts,
            "subscriptions": len(self._subscriptions),
        }
