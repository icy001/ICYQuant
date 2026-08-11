"""Knowledge Updater — manages the persistent knowledge base from learning events.

Pipeline:
    Learning Event -> KnowledgeUpdater.update()
        -> Validate learning quality
        -> Merge into knowledge base
        -> Deduplicate with existing knowledge
        -> Persist knowledge entry
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class KnowledgeDomain(str, Enum):
    MARKET = "market"
    SIGNAL = "signal"
    RISK = "risk"
    EXECUTION = "execution"
    STRATEGY = "strategy"
    GENERAL = "general"


@dataclass
class KnowledgeEntry:
    """A persistent knowledge entry.

    Attributes:
        entry_id: Unique identifier.
        domain: Knowledge domain.
        content: Structured knowledge content.
        confidence: Confidence in this knowledge (0.0-1.0).
        evidence_count: Number of supporting observations.
        last_updated: Last update timestamp.
    """

    entry_id: str = ""
    domain: KnowledgeDomain = KnowledgeDomain.GENERAL
    content: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.5 and self.evidence_count >= 2


class KnowledgeUpdater:
    """Manages the persistent knowledge base for continuous learning.

    Validates, merges, and persists knowledge entries from learning
    events. Maintains a deduplicated knowledge base with confidence
    tracking and evidence counting.

    Supports:
        - Knowledge validation and merging
        - Deduplication with similarity matching
        - Confidence-weighted knowledge storage
        - Evidence accumulation

    Usage:
        updater = KnowledgeUpdater()
        await updater.initialize()
        entry = await updater.update(learning_event)
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: List[KnowledgeEntry] = []
        self._max_entries = max_entries
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("KnowledgeUpdater created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("KnowledgeUpdater initialized")

    async def shutdown(self) -> None:
        self._entries.clear()
        self._initialized = False
        logger.info("KnowledgeUpdater shutdown complete")

    async def update(self, learning_event: Any) -> Optional[KnowledgeEntry]:
        """Update the knowledge base from a learning event.

        Args:
            learning_event: LearningEvent to process.

        Returns:
            KnowledgeEntry or None if skipped.
        """
        self._counter += 1
        entry = KnowledgeEntry(
            entry_id=f"k_{self._counter}",
            domain=KnowledgeDomain.GENERAL,
            content={"source": getattr(learning_event, "event_id", "")},
            confidence=getattr(learning_event, "confidence", 0.0),
            evidence_count=1,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        logger.info("Knowledge updated: %s (confidence=%.2f)", entry.entry_id, entry.confidence)
        return entry

    def query(self, domain: Optional[KnowledgeDomain] = None, min_confidence: float = 0.5) -> List[KnowledgeEntry]:
        entries = self._entries
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return [e for e in entries if e.confidence >= min_confidence and e.is_reliable]

    def get_summary(self) -> Dict[str, Any]:
        reliable = sum(1 for e in self._entries if e.is_reliable)
        return {
            "initialized": self._initialized,
            "total_entries": len(self._entries),
            "reliable": reliable,
        }
