"""
Memory manager orchestrating all memory layers.

Coordinates working, short-term, long-term, semantic, and episodic
memory with unified operations and cross-layer queries.

Architecture:
    Working Memory ← Short-Term Memory ← Long-Term Memory
                                         ├── Semantic Memory
                                         └── Episodic Memory
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.ai_agent.memory.working_memory import WorkingMemory
from services.ai_agent.memory.short_term_memory import ShortTermMemory
from services.ai_agent.memory.long_term_memory import (
    LongTermMemory,
    MemoryCategory,
    MemoryPriority,
)
from services.ai_agent.memory.semantic_memory import SemanticMemory, SemanticNode
from services.ai_agent.memory.episodic_memory import Episode, EpisodicMemory
from services.ai_agent.memory.memory_index import (
    IndexEntry,
    IndexEntryType,
    MemoryIndex,
)

logger = logging.getLogger(__name__)


# ── Config ──


@dataclass
class MemoryConfig:
    """Configuration for the memory subsystem."""

    working_memory_max_entries: int = 1000
    short_term_capacity: int = 1000
    short_term_default_ttl: float = 600.0
    long_term_enabled: bool = True
    semantic_enabled: bool = True
    episodic_enabled: bool = True
    episodic_max_episodes: int = 10000
    enable_indexing: bool = True
    auto_snapshot_enabled: bool = False


# ── Memory Manager ──


class MemoryManager:
    """Orchestrates all memory layers.

    Provides unified memory operations with automatic cascading
    across working → short-term → long-term memory.

    Usage:
        mgr = MemoryManager(config=MemoryConfig())
        mgr.working.set("current_price", 50000)
        mgr.short_term.put("cache_key", data, session_id="s1")
        knowledge = mgr.long_term.retrieve("market_hours")
    """

    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or MemoryConfig()

        # ── Memory Layers ──
        self.working = WorkingMemory(
            max_entries=self.config.working_memory_max_entries,
        )
        self.short_term = ShortTermMemory(
            capacity=self.config.short_term_capacity,
            default_ttl=self.config.short_term_default_ttl,
        )
        self.long_term = LongTermMemory()
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory(
            max_episodes=self.config.episodic_max_episodes,
        )

        # ── Index ──
        self.index = MemoryIndex()

        logger.info("MemoryManager created")

    # ── Unified Operations ──

    def remember(self, key: str, value: Any, persist: bool = False) -> None:
        """Store a value across memory layers.

        Always stored in working memory, optionally cached in short-term,
        and persisted to long-term if requested.

        Args:
            key: Storage key.
            value: Value to remember.
            persist: Whether to persist to long-term memory.
        """
        self.working.set(key, value)

        if persist:
            self.long_term.store(
                key=key,
                value=value,
                category=MemoryCategory.KNOWLEDGE,
                tags=["auto_stored"],
            )

    def recall(self, key: str, session_id: str = "") -> Any:
        """Retrieve a value, cascading through memory layers.

        Search order: Working → Short-Term → Long-Term

        Args:
            key: Lookup key.
            session_id: Optional session context for short-term.

        Returns:
            Found value or None.
        """
        # Layer 1: Working Memory
        if self.working.has(key):
            return self.working.get(key)

        # Layer 2: Short-Term Memory
        stm_value = self.short_term.get(key)
        if stm_value is not None:
            self.working.set(key, stm_value)  # Promote to working
            return stm_value

        # Layer 3: Long-Term Memory
        ltm_entry = self.long_term.retrieve(key)
        if ltm_entry is not None:
            self.working.set(key, ltm_entry.value)  # Promote to working
            return ltm_entry.value

        return None

    def forget(self, key: str) -> None:
        """Remove a key from all memory layers.

        Args:
            key: Key to forget.
        """
        self.working.delete(key)
        self.short_term.delete(key)
        self.long_term.delete(key)

    # ── Episode Recording ──

    def record_episode(self, episode: Episode) -> Episode:
        """Record an execution episode in episodic memory.

        Args:
            episode: The completed episode.

        Returns:
            The stored episode.
        """
        return self.episodic.record_episode(episode)

    def get_episode_history(
        self,
        session_id: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent episode history.

        Args:
            session_id: Optional session filter.
            limit: Maximum results.

        Returns:
            Episode summaries.
        """
        if session_id:
            episodes = self.episodic.get_by_session(session_id)
        else:
            episodes = self.episodic.get_recent(limit)

        return [e.to_dict() for e in episodes[:limit]]

    # ── Semantic Operations ──

    def add_knowledge(
        self,
        concept: str,
        node_type: str = "concept",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> SemanticNode:
        """Add a concept to semantic memory.

        Args:
            concept: Concept name.
            node_type: Type classification.
            attributes: Key-value attributes.

        Returns:
            The created node.
        """
        return self.semantic.add_concept(
            concept=concept,
            node_type=node_type,
            attributes=attributes,
        )

    # ── Maintenance ──

    def clear_session(self, session_id: str) -> None:
        """Clear all memory associated with a session.

        Args:
            session_id: Session identifier.
        """
        self.working.clear()
        removed = self.short_term.clear_session(session_id)
        logger.info(f"Cleared memory for session [{session_id}]: {removed} STM entries")

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive memory subsystem summary."""
        return {
            "working_memory": self.working.get_stats(),
            "short_term_memory": self.short_term.get_summary(),
            "long_term_memory": self.long_term.get_summary(),
            "semantic_memory": self.semantic.get_summary(),
            "episodic_memory": self.episodic.get_summary(),
            "index": self.index.get_summary(),
        }

    def get_total_size(self) -> int:
        """Total entries across all layers."""
        return (
            self.working.size
            + self.short_term.size
            + self.long_term.size
            + self.semantic.node_count
            + self.episodic.size
        )
