"""
ICYQuant Knowledge Engine — unified quantitative knowledge management system.

Powers the AI Research Assistant with semantic search, knowledge graph
traversal, and document indexing across research papers, market reports,
company filings, and internal documents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class KnowledgeDomain(str, Enum):
    RESEARCH_PAPER = "research_paper"
    MARKET_REPORT = "market_report"
    COMPANY_FILING = "company_filing"
    INTERNAL_DOCUMENT = "internal_document"
    NEWS_ARTICLE = "news_article"
    REGULATORY = "regulatory"


class DocumentStatus(str, Enum):
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    STALE = "stale"


@dataclass
class KnowledgeDocument:
    """A document stored in the knowledge engine."""
    doc_id: str
    title: str
    domain: KnowledgeDomain
    content: str
    source_url: str = ""
    authors: list[str] = field(default_factory=list)
    published_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    status: DocumentStatus = DocumentStatus.INDEXING
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None


@dataclass
class SearchResult:
    """A single search result with relevance score."""
    doc_id: str
    title: str
    domain: KnowledgeDomain
    snippet: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]
    total_found: int
    elapsed_ms: float


class KnowledgeEngine:
    """Unified quantitative knowledge management and retrieval system.

    Integrates:
        - Knowledge Graph (entity relationships)
        - Knowledge Index (document indexing)
        - Semantic Search (embedding-based retrieval)
        - Document Parser (multi-format ingestion)
        - Retrieval Engine (RAG-ready context assembly)

    Supports RAG (Retrieval-Augmented Generation) architecture:
        User Question → Embedding Search → Knowledge Ranking
        → Context Assembly → LLM
    """

    def __init__(self) -> None:
        self._documents: dict[str, KnowledgeDocument] = {}
        self._search_count = 0
        self._paused = False

    async def start(self) -> None:
        """Initialize the knowledge engine and load indices."""
        logger.info("Knowledge engine started")
        self._paused = False

    async def stop(self) -> None:
        """Shutdown the knowledge engine."""
        logger.info("Knowledge engine stopped")
        self._paused = True

    async def pause(self) -> None:
        self._paused = True

    async def resume(self) -> None:
        self._paused = False

    async def index_document(self, document: KnowledgeDocument) -> str:
        """Index a document into the knowledge base."""
        if document.doc_id in self._documents:
            logger.debug("Updating existing document %s", document.doc_id)
        document.indexed_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.INDEXED
        self._documents[document.doc_id] = document
        logger.info("Indexed document %s [%s]", document.doc_id, document.domain.value)
        return document.doc_id

    async def search(
        self,
        query: str,
        top_k: int = 10,
        context: Optional[dict[str, Any]] = None,
        domain_filter: Optional[list[KnowledgeDomain]] = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across the knowledge base.

        Returns ranked results with relevance scores.
        """
        self._search_count += 1

        # In production, this would use vector similarity search.
        # Here we do a simple text-match fallback.
        results: list[dict[str, Any]] = []
        query_lower = query.lower()

        for doc in self._documents.values():
            if doc.status != DocumentStatus.INDEXED:
                continue
            if domain_filter and doc.domain not in domain_filter:
                continue

            # Simple relevance scoring by keyword overlap
            content_lower = doc.content.lower()
            title_lower = doc.title.lower()

            title_match = query_lower in title_lower
            content_match = query_lower in content_lower
            score = 0.0
            if title_match:
                score = 0.9
            elif content_match:
                score = 0.5
            elif any(tag.lower() in query_lower for tag in doc.tags):
                score = 0.3

            if score > 0:
                results.append({
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "domain": doc.domain.value,
                    "snippet": doc.content[:500],
                    "score": score,
                    "source_url": doc.source_url,
                    "authors": doc.authors,
                    "tags": doc.tags,
                    "published_at": doc.published_at.isoformat() if doc.published_at else None,
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    async def get_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a document by ID."""
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        return {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "domain": doc.domain.value,
            "content": doc.content,
            "source_url": doc.source_url,
            "authors": doc.authors,
            "tags": doc.tags,
            "published_at": doc.published_at.isoformat() if doc.published_at else None,
            "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
            "metadata": doc.metadata,
        }

    async def delete_document(self, doc_id: str) -> bool:
        """Remove a document from the knowledge base."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        domains: dict[str, int] = {}
        for doc in self._documents.values():
            d = doc.domain.value
            domains[d] = domains.get(d, 0) + 1

        return {
            "total_documents": len(self._documents),
            "by_domain": domains,
            "total_searches": self._search_count,
            "paused": self._paused,
        }

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def is_paused(self) -> bool:
        return self._paused
