"""
Embedding Engine.

Semantic search and document similarity using embeddings:
- Document vectorization
- Semantic similarity search
- Topic clustering
- Nearest neighbor retrieval
"""

from __future__ import annotations

import logging
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class EmbeddingModel(str, Enum):
    TFIDF = "tfidf"
    KEYWORD_BASED = "keyword_based"
    EXTERNAL_API = "external_api"
    CUSTOM = "custom"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class DocumentEmbedding:
    """A document vector embedding."""

    embedding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    vector: List[float] = field(default_factory=list)
    dimension: int = 0
    model: EmbeddingModel = EmbeddingModel.KEYWORD_BASED

    # Metadata
    title: str = ""
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)

    # Timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Norm (cached for fast similarity)
    norm: float = 0.0

    def __post_init__(self):
        self.dimension = len(self.vector)
        if not self.norm and self.vector:
            self.norm = math.sqrt(sum(v * v for v in self.vector))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "embedding_id": self.embedding_id,
            "document_id": self.document_id,
            "dimension": self.dimension,
            "model": self.model.value,
            "title": self.title,
            "keywords": self.keywords,
            "symbols": self.symbols,
        }


@dataclass
class SimilarityResult:
    """Result of a similarity search."""

    embedding: DocumentEmbedding
    similarity: float
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.embedding.document_id,
            "title": self.embedding.title,
            "summary": self.embedding.summary,
            "similarity": self.similarity,
            "rank": self.rank,
            "keywords": self.embedding.keywords,
            "symbols": self.embedding.symbols,
        }


@dataclass
class SearchQuery:
    """A semantic search query."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    query_vector: List[float] = field(default_factory=list)

    # Filters
    symbols: Optional[List[str]] = None
    min_similarity: float = 0.0
    top_k: int = 10

    # Timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EmbeddingConfig:
    """Configuration for embedding engine."""

    # Model
    default_model: EmbeddingModel = EmbeddingModel.KEYWORD_BASED
    vector_dimension: int = 128

    # Similarity
    similarity_metric: str = "cosine"  # cosine, dot, euclidean

    # Search
    default_top_k: int = 10
    min_similarity: float = 0.1

    # Performance
    max_embeddings: int = 100000


# ── TF-IDF / Keyword-based Embedding ─────────────────────────────────────────

class KeywordEmbedder:
    """
    Keyword-based document embedder using TF-IDF-like vectorization.

    Creates sparse vector representations from document keywords
    with a fixed vocabulary for similarity comparison.
    """

    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self._vocabulary: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._doc_count: int = 0

    def _hash_to_dim(self, token: str) -> int:
        """Hash a token to a dimension index."""
        return hash(token) % self.dimension

    def vectorize(
        self, keywords: List[str], keyword_scores: Optional[Dict[str, float]] = None
    ) -> List[float]:
        """
        Convert keywords to a fixed-dimension vector.

        Uses hashing trick to map keyword features to fixed dimension,
        weighted by keyword scores (TF-IDF-like).
        """
        vector = [0.0] * self.dimension

        if not keyword_scores:
            # Uniform weights if no scores provided
            keyword_scores = {kw: 1.0 / len(keywords) for kw in keywords} if keywords else {}

        for kw, score in keyword_scores.items():
            dim = self._hash_to_dim(kw)
            # Accumulate weighted score
            vector[dim] += score

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def add_to_vocab(self, tokens: List[str]) -> None:
        """Update IDF-like statistics."""
        self._doc_count += 1
        for token in set(tokens):
            self._idf[token] = self._idf.get(token, 0) + 1


# ── Embedding Engine ─────────────────────────────────────────────────────────

class EmbeddingEngine:
    """
    Document embedding and semantic search engine.

    Supports:
    - Keyword-based vectorization
    - Cosine/dot/euclidean similarity
    - Semantic search with filtering
    - Nearest neighbor retrieval
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._embeddings: Dict[str, DocumentEmbedding] = {}
        self._symbol_index: Dict[str, List[str]] = defaultdict(list)
        self._embedder = KeywordEmbedder(self.config.vector_dimension)

    # ── Embedding Creation ───────────────────────────────────────────────────

    def embed(
        self,
        document_id: str,
        keywords: List[str],
        keyword_scores: Optional[Dict[str, float]] = None,
        title: str = "",
        summary: str = "",
        symbols: Optional[List[str]] = None,
        model: Optional[EmbeddingModel] = None,
    ) -> DocumentEmbedding:
        """
        Create an embedding for a document.

        Args:
            document_id: Document identifier.
            keywords: Extracted keywords.
            keyword_scores: Keyword importance scores.
            title: Document title.
            summary: Document summary.
            symbols: Related stock symbols.
            model: Embedding model to use.

        Returns:
            DocumentEmbedding with computed vector.
        """
        # Compute vector
        vector = self._embedder.vectorize(keywords, keyword_scores)

        embedding = DocumentEmbedding(
            document_id=document_id,
            vector=vector,
            dimension=len(vector),
            model=model or self.config.default_model,
            title=title,
            summary=summary,
            keywords=keywords,
            symbols=symbols or [],
        )

        # Store
        self._embeddings[embedding.embedding_id] = embedding

        # Index by symbol
        for sym in embedding.symbols:
            self._symbol_index[sym.upper()].append(embedding.embedding_id)

        # Update vocabulary stats
        self._embedder.add_to_vocab(keywords)

        return embedding

    def embed_batch(
        self,
        documents: List[Tuple[str, List[str], Optional[Dict[str, float]], str, str, Optional[List[str]]]],
    ) -> List[DocumentEmbedding]:
        """Batch embed documents."""
        return [
            self.embed(doc_id, kw, scores, title, summary, symbols)
            for doc_id, kw, scores, title, summary, symbols in documents
        ]

    # ── Similarity Computation ───────────────────────────────────────────────

    def cosine_similarity(
        self, vec_a: List[float], vec_b: List[float]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def dot_product(
        self, vec_a: List[float], vec_b: List[float]
    ) -> float:
        """Compute dot product similarity."""
        return sum(a * b for a, b in zip(vec_a, vec_b))

    def euclidean_similarity(
        self, vec_a: List[float], vec_b: List[float]
    ) -> float:
        """Compute euclidean-distance-based similarity."""
        squared_diff = sum((a - b) ** 2 for a, b in zip(vec_a, vec_b))
        distance = math.sqrt(squared_diff)
        # Convert distance to similarity [0, 1]
        return 1.0 / (1.0 + distance)

    def compute_similarity(
        self, vec_a: List[float], vec_b: List[float]
    ) -> float:
        """Compute similarity using configured metric."""
        metric = self.config.similarity_metric
        if metric == "cosine":
            return self.cosine_similarity(vec_a, vec_b)
        elif metric == "dot":
            return self.dot_product(vec_a, vec_b)
        elif metric == "euclidean":
            return self.euclidean_similarity(vec_a, vec_b)
        else:
            return self.cosine_similarity(vec_a, vec_b)

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self, query: SearchQuery
    ) -> List[SimilarityResult]:
        """
        Semantic search over embeddings.

        Args:
            query: Search query with text or vector.

        Returns:
            Ranked list of SimilarityResult.
        """
        # Compute query vector if needed
        if not query.query_vector and query.text:
            keywords = query.text.lower().split()
            query.query_vector = self._embedder.vectorize(
                keywords,
                {kw: 1.0 for kw in keywords},
            )

        if not query.query_vector:
            return []

        results: List[SimilarityResult] = []

        for emb_id, embedding in self._embeddings.items():
            # Symbol filter
            if query.symbols:
                sym_set = set(s.upper() for s in query.symbols)
                emb_sym_set = set(s.upper() for s in embedding.symbols)
                if not sym_set & emb_sym_set:
                    continue

            # Compute similarity
            sim = self.compute_similarity(query.query_vector, embedding.vector)

            if sim >= (query.min_similarity or self.config.min_similarity):
                results.append(SimilarityResult(
                    embedding=embedding,
                    similarity=sim,
                ))

        # Sort and rank
        results.sort(key=lambda r: r.similarity, reverse=True)
        for i, r in enumerate(results[: query.top_k]):
            r.rank = i + 1

        return results[: query.top_k]

    def search_by_text(
        self,
        text: str,
        symbols: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[SimilarityResult]:
        """Convenience method: search by text string."""
        query = SearchQuery(
            text=text,
            symbols=symbols,
            top_k=top_k,
        )
        return self.search(query)

    def find_similar(
        self,
        document_id: str,
        top_k: int = 10,
    ) -> List[SimilarityResult]:
        """Find documents similar to a given document."""
        # Find the target embedding
        target_emb = None
        for emb in self._embeddings.values():
            if emb.document_id == document_id:
                target_emb = emb
                break

        if not target_emb:
            return []

        query = SearchQuery(
            query_vector=target_emb.vector,
            top_k=top_k + 1,  # +1 to account for self-match
        )
        results = self.search(query)

        # Remove self-match
        return [
            r for r in results
            if r.embedding.document_id != document_id
        ][:top_k]

    # ── Clustering (simple) ──────────────────────────────────────────────────

    def cluster_by_similarity(
        self, threshold: float = 0.5
    ) -> List[List[str]]:
        """
        Simple clustering by similarity threshold.

        Returns:
            List of clusters, each cluster is a list of document IDs.
        """
        doc_ids = list(set(e.document_id for e in self._embeddings.values()))
        visited: Set[str] = set()
        clusters: List[List[str]] = []

        for doc_id in doc_ids:
            if doc_id in visited:
                continue

            cluster = [doc_id]
            visited.add(doc_id)

            # Find all similar docs
            similar = self.find_similar(doc_id, top_k=len(doc_ids))
            for result in similar:
                if result.similarity >= threshold and result.embedding.document_id not in visited:
                    cluster.append(result.embedding.document_id)
                    visited.add(result.embedding.document_id)

            clusters.append(cluster)

        return clusters

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_embedding(self, embedding_id: str) -> Optional[DocumentEmbedding]:
        """Get embedding by ID."""
        return self._embeddings.get(embedding_id)

    def get_by_symbol(self, symbol: str) -> List[DocumentEmbedding]:
        """Get all embeddings for a symbol."""
        ids = self._symbol_index.get(symbol.upper(), [])
        return [self._embeddings[eid] for eid in ids if eid in self._embeddings]

    @property
    def embedding_count(self) -> int:
        return len(self._embeddings)

    def clear(self) -> None:
        """Clear all embeddings."""
        self._embeddings.clear()
        self._symbol_index.clear()
