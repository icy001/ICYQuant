"""
Vector Store Infrastructure.

Persistent storage and retrieval of document embeddings
with support for approximate nearest neighbor (ANN) search.
"""

from __future__ import annotations

import logging
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class VectorDistance(str, Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class StoredVector:
    """A vector stored in the vector store."""

    vector_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    values: List[float] = field(default_factory=list)
    dimension: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    stored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Precomputed norm
    _norm: Optional[float] = None

    @property
    def norm(self) -> float:
        if self._norm is None and self.values:
            self._norm = math.sqrt(sum(v * v for v in self.values))
        return self._norm or 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "dimension": self.dimension,
            "metadata": self.metadata,
        }


@dataclass
class VectorIndex:
    """A named index grouping vectors for search."""

    index_name: str = "default"
    vector_ids: List[str] = field(default_factory=list)
    dimension: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VectorConfig:
    """Configuration for the vector store."""

    default_index: str = "default"
    distance_metric: VectorDistance = VectorDistance.COSINE
    max_vectors_per_index: int = 100000
    search_top_k: int = 100


# ── Vector Store ─────────────────────────────────────────────────────────────

class VectorStore:
    """
    In-memory vector store with similarity search.

    Supports:
    - Multiple named indexes
    - Cosine, Euclidean, and Dot Product similarity
    - Brute-force search (exact nearest neighbors)
    - Metadata filtering
    """

    def __init__(self, config: Optional[VectorConfig] = None):
        self.config = config or VectorConfig()
        self._vectors: Dict[str, StoredVector] = {}
        self._indexes: Dict[str, VectorIndex] = {}
        self._ensure_default_index()

    def _ensure_default_index(self) -> None:
        if self.config.default_index not in self._indexes:
            self._indexes[self.config.default_index] = VectorIndex(
                index_name=self.config.default_index
            )

    # ── Vector CRUD ──────────────────────────────────────────────────────────

    def put(
        self,
        values: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        vector_id: Optional[str] = None,
        index_name: Optional[str] = None,
    ) -> str:
        """
        Store a vector.

        Args:
            values: Vector values.
            metadata: Associated metadata.
            vector_id: Optional explicit ID.
            index_name: Target index name.

        Returns:
            vector_id of the stored vector.
        """
        idx_name = index_name or self.config.default_index
        if idx_name not in self._indexes:
            self._indexes[idx_name] = VectorIndex(index_name=idx_name)

        vec = StoredVector(
            vector_id=vector_id or str(uuid.uuid4()),
            values=list(values),
            dimension=len(values),
            metadata=metadata or {},
        )

        self._vectors[vec.vector_id] = vec
        self._indexes[idx_name].vector_ids.append(vec.vector_id)
        self._indexes[idx_name].dimension = max(
            self._indexes[idx_name].dimension, vec.dimension
        )

        return vec.vector_id

    def put_batch(
        self,
        vectors: List[Tuple[List[float], Optional[Dict[str, Any]]]],
        index_name: Optional[str] = None,
    ) -> List[str]:
        """Batch store vectors."""
        return [
            self.put(values, metadata, index_name=index_name)
            for values, metadata in vectors
        ]

    def get(self, vector_id: str) -> Optional[StoredVector]:
        """Get a vector by ID."""
        return self._vectors.get(vector_id)

    def delete(self, vector_id: str) -> bool:
        """Delete a vector."""
        if vector_id not in self._vectors:
            return False

        del self._vectors[vector_id]
        for index in self._indexes.values():
            if vector_id in index.vector_ids:
                index.vector_ids.remove(vector_id)

        return True

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: List[float],
        top_k: int = 10,
        index_name: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search for nearest neighbors.

        Args:
            query: Query vector.
            top_k: Number of results.
            index_name: Index to search.
            metadata_filter: Filter by metadata equality.
            min_similarity: Minimum similarity threshold.

        Returns:
            List of (vector_id, similarity, metadata) tuples.
        """
        idx_name = index_name or self.config.default_index
        index = self._indexes.get(idx_name)
        if not index:
            return []

        # Compute distances to all vectors in the index
        results: List[Tuple[str, float]] = []
        query_norm = math.sqrt(sum(v * v for v in query))

        for vid in index.vector_ids:
            vec = self._vectors.get(vid)
            if not vec:
                continue

            # Metadata filter
            if metadata_filter:
                if not all(
                    vec.metadata.get(k) == v
                    for k, v in metadata_filter.items()
                ):
                    continue

            # Compute similarity
            if self.config.distance_metric == VectorDistance.COSINE:
                sim = self._cosine_similarity(query, query_norm, vec.values, vec.norm)
            elif self.config.distance_metric == VectorDistance.EUCLIDEAN:
                sim = self._euclidean_similarity(query, vec.values)
            elif self.config.distance_metric == VectorDistance.DOT_PRODUCT:
                sim = self._dot_product(query, vec.values)
            else:
                sim = self._cosine_similarity(query, query_norm, vec.values, vec.norm)

            if sim >= min_similarity:
                results.append((vid, sim))

        # Sort descending by similarity
        results.sort(key=lambda x: x[1], reverse=True)

        return [
            (vid, sim, self._vectors[vid].metadata)
            for vid, sim in results[:top_k]
        ]

    def search_by_metadata(
        self, metadata_filter: Dict[str, Any], top_k: int = 10
    ) -> List[StoredVector]:
        """Find vectors by exact metadata match."""
        results = []
        for vec in self._vectors.values():
            if all(
                vec.metadata.get(k) == v
                for k, v in metadata_filter.items()
            ):
                results.append(vec)
        return results[:top_k]

    # ── Similarity Functions ─────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(
        a: List[float], a_norm: float, b: List[float], b_norm: float
    ) -> float:
        if a_norm == 0 or b_norm == 0:
            return 0.0
        dot = sum(av * bv for av, bv in zip(a, b))
        return dot / (a_norm * b_norm)

    @staticmethod
    def _euclidean_similarity(a: List[float], b: List[float]) -> float:
        dist = math.sqrt(sum((av - bv) ** 2 for av, bv in zip(a, b)))
        return 1.0 / (1.0 + dist)

    @staticmethod
    def _dot_product(a: List[float], b: List[float]) -> float:
        return sum(av * bv for av, bv in zip(a, b))

    # ── Index Operations ─────────────────────────────────────────────────────

    def create_index(self, index_name: str) -> VectorIndex:
        """Create a named index."""
        if index_name in self._indexes:
            return self._indexes[index_name]
        idx = VectorIndex(index_name=index_name)
        self._indexes[index_name] = idx
        return idx

    def list_indexes(self) -> List[str]:
        """List all index names."""
        return list(self._indexes.keys())

    def delete_index(self, index_name: str) -> bool:
        """Delete an index and all its vectors."""
        if index_name == self.config.default_index:
            logger.warning("Cannot delete default index")
            return False

        index = self._indexes.pop(index_name, None)
        if index:
            for vid in index.vector_ids:
                self._vectors.pop(vid, None)

        return index is not None

    # ── Stats ────────────────────────────────────────────────────────────────

    @property
    def vector_count(self) -> int:
        return len(self._vectors)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_vectors": len(self._vectors),
            "indexes": {
                name: {"count": len(idx.vector_ids), "dimension": idx.dimension}
                for name, idx in self._indexes.items()
            },
        }

    def clear(self) -> None:
        """Clear all vectors and indexes."""
        self._vectors.clear()
        self._indexes.clear()
        self._ensure_default_index()
