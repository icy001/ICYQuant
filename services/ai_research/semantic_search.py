"""
ICYQuant Semantic Search — embedding-based semantic search for research documents.

Converts text queries and documents into vector embeddings for
semantic similarity matching, supporting multi-language and
domain-specific search.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """A semantic search query."""
    text: str
    embedding: Optional[list[float]] = None
    filters: dict[str, Any] = field(default_factory=dict)
    top_k: int = 10
    min_score: float = 0.5


@dataclass
class SearchHit:
    """A single search hit."""
    doc_id: str
    score: float
    text_snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticSearch:
    """Embedding-based semantic search engine.

    Uses vector embeddings for similarity-based document retrieval,
    supporting:
        - Query embedding generation
        - Cosine similarity ranking
        - Domain-specific filtering
        - Hybrid search (lexical + semantic)
    """

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, Any]] = {}
        self._query_count = 0

    def index(
        self,
        doc_id: str,
        text: str,
        embedding: Optional[list[float]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Index a document for semantic search."""
        self._documents[doc_id] = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
            "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        }
        return doc_id

    def search(self, query: SearchQuery) -> list[SearchHit]:
        """Execute a semantic search query."""
        self._query_count += 1

        if query.embedding is None:
            # Fallback to keyword matching
            return self._keyword_search(query)

        results: list[SearchHit] = []

        for doc_id, doc in self._documents.items():
            if doc["embedding"] is None:
                continue

            # Apply filters
            if not self._matches_filters(doc["metadata"], query.filters):
                continue

            score = self._cosine_similarity(query.embedding, doc["embedding"])
            if score >= query.min_score:
                results.append(SearchHit(
                    doc_id=doc_id,
                    score=score,
                    text_snippet=doc["text"][:300],
                    metadata=doc["metadata"],
                ))

        results.sort(key=lambda h: h.score, reverse=True)
        return results[:query.top_k]

    def _keyword_search(self, query: SearchQuery) -> list[SearchHit]:
        """Fallback keyword search when no embedding is available."""
        results: list[SearchHit] = []
        query_lower = query.text.lower()

        for doc_id, doc in self._documents.items():
            if not self._matches_filters(doc["metadata"], query.filters):
                continue
            text_lower = doc["text"].lower()
            if query_lower in text_lower:
                # Simple overlap score
                score = min(1.0, len(query_lower) / max(1, len(text_lower)) * 10)
                if score >= query.min_score:
                    results.append(SearchHit(
                        doc_id=doc_id,
                        score=score,
                        text_snippet=doc["text"][:300],
                        metadata=doc["metadata"],
                    ))

        results.sort(key=lambda h: h.score, reverse=True)
        return results[:query.top_k]

    def remove(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    @staticmethod
    def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True

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
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def total_queries(self) -> int:
        return self._query_count
