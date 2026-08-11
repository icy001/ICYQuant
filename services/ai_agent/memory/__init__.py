"""
Agent memory subsystem.

Hierarchical memory architecture:
    Working Memory → Short-Term Memory → Long-Term Memory
                                           ├── Semantic Memory
                                           └── Episodic Memory

Each layer serves distinct retention windows and retrieval patterns,
enabling efficient context management for agent operations.
"""

from __future__ import annotations

from services.ai_agent.memory.working_memory import WorkingMemory
from services.ai_agent.memory.short_term_memory import ShortTermMemory
from services.ai_agent.memory.long_term_memory import LongTermMemory
from services.ai_agent.memory.semantic_memory import SemanticMemory, SemanticNode
from services.ai_agent.memory.episodic_memory import EpisodicMemory, Episode
from services.ai_agent.memory.memory_manager import MemoryManager, MemoryConfig
from services.ai_agent.memory.memory_index import MemoryIndex
from services.ai_agent.memory.memory_snapshot import MemorySnapshot, SnapshotManager

__all__ = [
    "WorkingMemory",
    "ShortTermMemory",
    "LongTermMemory",
    "SemanticMemory",
    "SemanticNode",
    "EpisodicMemory",
    "Episode",
    "MemoryManager",
    "MemoryConfig",
    "MemoryIndex",
    "MemorySnapshot",
    "SnapshotManager",
]
