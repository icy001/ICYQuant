"""Agent Memory - short-term and long-term memory for agents.

Provides experience storage, episodic memory, and working memory
for agents to learn from past decisions and observations.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    EPISODIC = "episodic"      # Past experiences / events
    SEMANTIC = "semantic"      # Facts / knowledge
    WORKING = "working"        # Current context / active
    PROCEDURAL = "procedural"  # Learned behaviors / rules


class MemoryImportance(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class MemoryItem:
    """A single memory entry."""

    memory_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    mem_type: MemoryType = MemoryType.EPISODIC
    content: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    importance: MemoryImportance = MemoryImportance.NORMAL
    timestamp: float = field(default_factory=time.time)
    ttl: Optional[float] = None  # seconds until expiry
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    def access(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return (time.time() - self.timestamp) > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "type": self.mem_type.value,
            "content": self.content,
            "context": self.context,
            "importance": self.importance.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


class AgentMemory:
    """Multi-layer memory system for agents.

    Layers:
    - Working memory: current observation, active goals (small, fast)
    - Episodic memory: past experiences with outcomes
    - Semantic memory: learned facts and relationships
    - Procedural memory: learned behavioral rules
    """

    def __init__(self, agent_name: str = "", capacity: int = 10000):
        self.agent_name = agent_name
        self.capacity = capacity
        self._working: Dict[str, Any] = {}
        self._episodic: List[MemoryItem] = []
        self._semantic: Dict[str, Any] = {}
        self._procedural: List[Dict[str, Any]] = []
        self._all_memories: List[MemoryItem] = []

    # ── Working Memory ──────────────────────────────────────────

    def set_working(self, key: str, value: Any) -> None:
        """Set a working memory entry."""
        self._working[key] = value

    def get_working(self, key: str, default: Any = None) -> Any:
        """Get a working memory entry."""
        return self._working.get(key, default)

    def clear_working(self) -> None:
        """Clear working memory."""
        self._working.clear()

    def get_working_context(self) -> Dict[str, Any]:
        """Get the full working memory context."""
        return dict(self._working)

    # ── Episodic Memory ─────────────────────────────────────────

    def remember_episode(
        self,
        content: Any,
        context: Dict[str, Any] = None,
        importance: MemoryImportance = MemoryImportance.NORMAL,
        tags: List[str] = None,
        ttl: Optional[float] = None,
    ) -> str:
        """Store an episodic memory."""
        item = MemoryItem(
            mem_type=MemoryType.EPISODIC,
            content=content,
            context=context or {},
            importance=importance,
            tags=tags or [],
            ttl=ttl,
        )
        self._episodic.append(item)
        self._all_memories.append(item)
        self._prune()
        return item.memory_id

    def recall_episodes(
        self,
        tags: List[str] = None,
        min_importance: MemoryImportance = None,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[MemoryItem]:
        """Recall episodic memories matching criteria."""
        results = []
        for item in reversed(self._episodic):
            if item.is_expired():
                continue
            if tags and not any(t in item.tags for t in tags):
                continue
            if min_importance and item.importance.value < min_importance.value:
                continue
            if since and item.timestamp < since:
                continue
            item.access()
            results.append(item)
            if len(results) >= limit:
                break
        return list(reversed(results))

    def recall_recent(self, n: int = 10) -> List[MemoryItem]:
        """Recall the n most recent episodes."""
        valid = [m for m in self._episodic if not m.is_expired()]
        return valid[-n:]

    # ── Semantic Memory ─────────────────────────────────────────

    def learn_fact(self, key: str, value: Any, confidence: float = 1.0) -> None:
        """Store a semantic fact with confidence."""
        self._semantic[key] = {"value": value, "confidence": confidence, "timestamp": time.time()}

    def recall_fact(self, key: str) -> Optional[Dict[str, Any]]:
        """Recall a semantic fact."""
        return self._semantic.get(key)

    def get_all_facts(self) -> Dict[str, Any]:
        """Get all semantic facts."""
        return {k: v["value"] for k, v in self._semantic.items()}

    # ── Procedural Memory ───────────────────────────────────────

    def learn_rule(self, condition: str, action: str, confidence: float = 1.0) -> None:
        """Store a procedural rule."""
        self._procedural.append({
            "condition": condition,
            "action": action,
            "confidence": confidence,
            "timestamp": time.time(),
        })

    def get_rules(self, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
        """Get all procedural rules."""
        return [r for r in self._procedural if r["confidence"] >= min_confidence]

    # ── Experience-based Learning ───────────────────────────────

    def learn_from_outcome(
        self,
        decision: Dict[str, Any],
        outcome: str,
        reward: float,
        context: Dict[str, Any] = None,
    ) -> None:
        """Learn from a decision outcome - stores episode and updates rules."""
        episode_content = {
            "decision": decision,
            "outcome": outcome,
            "reward": reward,
            "context": context,
        }
        importance = MemoryImportance.HIGH if abs(reward) > 0.5 else MemoryImportance.NORMAL
        tags = ["outcome", outcome]
        if reward > 0:
            tags.append("success")
        elif reward < 0:
            tags.append("failure")

        self.remember_episode(
            content=episode_content,
            context=context or {},
            importance=importance,
            tags=tags,
        )

        # Learn procedural rule from outcome
        if reward > 0.3:
            self.learn_rule(
                condition=str(decision),
                action=outcome,
                confidence=min(1.0, abs(reward)),
            )

    def get_successful_episodes(self, limit: int = 20) -> List[MemoryItem]:
        """Get episodes tagged as successful."""
        return self.recall_episodes(tags=["success"], limit=limit)

    def get_failure_episodes(self, limit: int = 20) -> List[MemoryItem]:
        """Get episodes tagged as failures."""
        return self.recall_episodes(tags=["failure"], limit=limit)

    # ── Maintenance ─────────────────────────────────────────────

    def _prune(self) -> None:
        """Remove old/expired memories to maintain capacity."""
        # Remove expired
        self._all_memories = [m for m in self._all_memories if not m.is_expired()]
        self._episodic = [m for m in self._episodic if not m.is_expired()]
        # Enforce capacity - remove lowest importance first
        while len(self._all_memories) > self.capacity:
            self._all_memories.sort(key=lambda m: (m.importance.value, m.access_count))
            removed = self._all_memories.pop(0)
            if removed in self._episodic:
                self._episodic.remove(removed)

    def clear(self) -> None:
        """Clear all memory."""
        self._working.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._procedural.clear()
        self._all_memories.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "working_keys": len(self._working),
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "procedural_count": len(self._procedural),
            "total_items": len(self._all_memories),
            "success_count": len(self.get_successful_episodes(limit=999999)),
            "failure_count": len(self.get_failure_episodes(limit=999999)),
        }

    @property
    def total_memories(self) -> int:
        return len(self._all_memories)
