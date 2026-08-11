"""
ICYQuant Knowledge Index — inverted index and vector index for fast knowledge retrieval.

Provides dual-index architecture:
    - Lexical index (keyword-based, fast exact match)
    - Semantic index (embedding-based, semantic similarity)

Used by the Knowledge Engine for efficient document lookup.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class IndexEntry:
    """An entry in the knowledge index."""
    doc_id: str
    title: str
    domain: str
    tokens: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeIndex:
    """Dual-index (lexical + semantic) for knowledge retrieval.

    Lexical index: inverted index mapping token → document IDs
    Semantic index: vector embeddings for cosine similarity search
    """

    def __init__(self) -> None:
        # Lexical: token → set of doc_ids
        self._inverted_index: dict[str, set[str]] = defaultdict(set)
        # Semantic: doc_id → embedding vector
        self._embeddings: dict[str, list[float]] = {}
        # Full entries
        self._entries: dict[str, IndexEntry] = {}

    def index(self, entry: IndexEntry) -> None:
        """Add an entry to both indices."""
        # Remove old entry if re-indexing
        if entry.doc_id in self._entries:
            self._remove_from_lexical(entry.doc_id)

        self._entries[entry.doc_id] = entry

        # Lexical index
        for token in entry.tokens:
            self._inverted_index[token.lower()].add(entry.doc_id)

        # Semantic index
        if entry.embedding is not None:
            self._embeddings[entry.doc_id] = entry.embedding

    def remove(self, doc_id: str) -> bool:
        """Remove an entry from all indices."""
        if doc_id not in self._entries:
            return False
        self._remove_from_lexical(doc_id)
        self._embeddings.pop(doc_id, None)
        del self._entries[doc_id]
        return True

    def search_lexical(self, query: str, limit: int = 10) -> list[str]:
        """Lexical search: token-based exact matching."""
        tokens = query.lower().split()
        if not tokens:
            return []

        # Intersection of token matches
        result_sets = [self._inverted_index.get(t, set()) for t in tokens]
        if not result_sets:
            return []

        matched = result_sets[0].copy()
        for s in result_sets[1:]:
            matched &= s

        return list(matched)[:limit]

    def search_semantic(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[tuple[str, float]]:
        """Semantic search: cosine similarity over embeddings."""
        results: list[tuple[str, float]] = []

        for doc_id, embedding in self._embeddings.items():
            similarity = self._cosine_similarity(query_embedding, embedding)
            if similarity >= threshold:
                results.append((doc_id, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_entry(self, doc_id: str) -> Optional[IndexEntry]:
        return self._entries.get(doc_id)

    def _remove_from_lexical(self, doc_id: str) -> None:
        """Remove a document from the inverted index."""
        entry = self._entries.get(doc_id)
        if entry:
            for token in entry.tokens:
                token_set = self._inverted_index.get(token.lower())
                if token_set:
                    token_set.discard(doc_id)
                    if not token_set:
                        del self._inverted_index[token.lower()]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def token_count(self) -> int:
        return len(self._inverted_index)
