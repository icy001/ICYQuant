"""
ICYQuant Retrieval Engine — RAG-ready context assembly for LLM-powered research.

Assembles retrieved documents into structured context blocks suitable
for LLM consumption, with chunking, deduplication, and relevance ranking.

Supports the full RAG pipeline:
    User Question → Embedding Search → Knowledge Ranking
    → Context Assembly → LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """Assembled context ready for LLM consumption."""
    query: str
    chunks: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 4096
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RetrievalConfig:
    max_chunks: int = 20
    chunk_size: int = 1000
    chunk_overlap: int = 100
    max_context_tokens: int = 4096
    deduplicate: bool = True


class RetrievalEngine:
    """RAG-ready retrieval and context assembly engine.

    Responsibilities:
        - Chunk documents into LLM-friendly segments
        - Deduplicate overlapping content
        - Rank by relevance and diversity
        - Assemble into structured context blocks
        - Track source provenance for citations
    """

    def __init__(self, config: Optional[RetrievalConfig] = None) -> None:
        self._config = config or RetrievalConfig()
        self._retrieval_count = 0

    async def retrieve(
        self,
        query: str,
        documents: list[dict[str, Any]],
        context: Optional[dict[str, Any]] = None,
    ) -> RetrievalContext:
        """Retrieve and assemble context from documents for a given query.

        Args:
            query: The user's research question
            documents: Raw documents from semantic search
            context: Additional filtering/ranking context

        Returns:
            Structured RetrievalContext ready for LLM prompt assembly
        """
        self._retrieval_count += 1

        # Step 1: Chunk documents
        chunks = self._chunk_documents(documents)

        # Step 2: Deduplicate
        if self._config.deduplicate:
            chunks = self._deduplicate(chunks)

        # Step 3: Rank by relevance
        ranked = self._rank_chunks(query, chunks)

        # Step 4: Assemble context within token budget
        assembled = self._assemble(query, ranked)

        return assembled

    def _chunk_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Split documents into overlapping chunks."""
        chunks: list[dict[str, Any]] = []
        for doc in documents:
            content = doc.get("content") or doc.get("snippet") or ""
            doc_id = doc.get("doc_id", "")
            title = doc.get("title", "")
            domain = doc.get("domain", "")

            if len(content) <= self._config.chunk_size:
                chunks.append({
                    "doc_id": doc_id,
                    "title": title,
                    "domain": domain,
                    "content": content,
                    "chunk_index": 0,
                    "source_url": doc.get("source_url", ""),
                    "authors": doc.get("authors", []),
                })
            else:
                step = self._config.chunk_size - self._config.chunk_overlap
                for i in range(0, len(content), step):
                    chunk_content = content[i:i + self._config.chunk_size]
                    chunks.append({
                        "doc_id": doc_id,
                        "title": title,
                        "domain": domain,
                        "content": chunk_content,
                        "chunk_index": i // step,
                        "source_url": doc.get("source_url", ""),
                        "authors": doc.get("authors", []),
                    })
        return chunks

    def _deduplicate(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate or near-duplicate chunks."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for chunk in chunks:
            # Simple fingerprint: first 100 chars normalized
            fingerprint = chunk["content"][:100].strip().lower()
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(chunk)
        return unique

    def _rank_chunks(
        self,
        query: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank chunks by relevance to the query."""
        query_lower = query.lower()
        scored: list[tuple[float, dict[str, Any]]] = []

        for chunk in chunks:
            content_lower = chunk["content"].lower()
            # Simple keyword overlap score
            query_terms = set(query_lower.split())
            content_terms = set(content_lower.split())
            overlap = len(query_terms & content_terms)
            score = overlap / max(1, len(query_terms))

            # Title bonus
            title_lower = chunk.get("title", "").lower()
            if query_lower in title_lower:
                score += 0.3

            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:self._config.max_chunks]]

    def _assemble(self, query: str, chunks: list[dict[str, Any]]) -> RetrievalContext:
        """Assemble ranked chunks into a token-budgeted context."""
        ctx = RetrievalContext(query=query, max_tokens=self._config.max_context_tokens)
        token_count = 0
        seen_sources: set[str] = set()

        for chunk in chunks:
            estimated_tokens = len(chunk["content"]) // 4  # Rough estimate
            if token_count + estimated_tokens > self._config.max_context_tokens:
                break

            ctx.chunks.append(chunk)
            token_count += estimated_tokens

            # Track unique sources
            source_key = f"{chunk['doc_id']}_{chunk['chunk_index']}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                ctx.sources.append({
                    "doc_id": chunk["doc_id"],
                    "title": chunk["title"],
                    "domain": chunk["domain"],
                    "source_url": chunk.get("source_url", ""),
                    "authors": chunk.get("authors", []),
                })

        ctx.total_tokens = token_count
        return ctx

    @property
    def retrieval_count(self) -> int:
        return self._retrieval_count
