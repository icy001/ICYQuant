"""Alternative Intelligence Memory — stores and retrieves historical alternative data analysis results."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeRecord,
    MemoryEntry,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class MemoryQueryResult:
    """Result of querying the alternative intelligence memory."""

    entries: list[MemoryEntry] = field(default_factory=list)
    total_matches: int = 0
    query: str = ""

    @property
    def best_match(self) -> MemoryEntry | None:
        return self.entries[0] if self.entries else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AlternativeMemory:
    """Stores and retrieves historical alternative intelligence analysis for learning.

    Capabilities:
    - Store analysis results with metadata
    - Retrieve by source, asset, time range
    - Similarity-based search
    - Performance tracking (realized alpha)
    - Usage statistics (retrieval counts)
    """

    def __init__(self) -> None:
        self.records: list[MemoryEntry] = []
        self._source_index: dict[str, list[int]] = defaultdict(list)
        self._asset_index: dict[str, list[int]] = defaultdict(list)
        self._tag_index: dict[str, list[int]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, item: MemoryEntry | AlternativeRecord | dict) -> MemoryEntry:
        """Save an item to the alternative memory.

        Accepts MemoryEntry, AlternativeRecord, or dict.
        For dict, expects keys matching MemoryEntry fields.
        """
        if isinstance(item, MemoryEntry):
            entry = item
        elif isinstance(item, AlternativeRecord):
            entry = MemoryEntry(record=item)
        elif isinstance(item, dict):
            entry = MemoryEntry(**item)
        else:
            raise TypeError(f"Unsupported item type: {type(item)}")

        idx = len(self.records)
        self.records.append(entry)

        # Update indices
        self._source_index[entry.record.source].append(idx)
        for tag in entry.record.asset_tags:
            self._asset_index[tag].append(idx)
        for key in entry.record.metadata:
            self._tag_index[key].append(idx)

        return entry

    def save_analysis(
        self,
        record: AlternativeRecord,
        analysis_result: dict,
        alpha_performance: float | None = None,
    ) -> MemoryEntry:
        """Convenience method to save a record with analysis result."""
        entry = MemoryEntry(
            record=record,
            analysis_result=analysis_result,
            alpha_performance=alpha_performance,
        )
        return self.save(entry)

    def query(
        self,
        source: str | None = None,
        asset: str | None = None,
        min_relevance: float = 0.0,
        limit: int = 100,
    ) -> MemoryQueryResult:
        """Query the memory by source and/or asset filters."""
        candidate_indices: set[int] = set()

        # Source filter
        if source:
            source_indices = set(self._source_index.get(source, []))
            if candidate_indices:
                candidate_indices &= source_indices
            else:
                candidate_indices = source_indices

        # Asset filter
        if asset:
            asset_indices = set(self._asset_index.get(asset, []))
            if candidate_indices:
                candidate_indices &= asset_indices
            else:
                candidate_indices = asset_indices

        # No filters → all records
        if not source and not asset:
            candidate_indices = set(range(len(self.records)))

        # Collect and filter by relevance
        entries = []
        for idx in sorted(candidate_indices):
            entry = self.records[idx]
            if entry.relevance_score >= min_relevance:
                entries.append(entry)
                entry.retrieval_count += 1

        # Sort by relevance descending
        entries.sort(key=lambda e: e.relevance_score, reverse=True)

        query_desc_parts = []
        if source:
            query_desc_parts.append(f"source={source}")
        if asset:
            query_desc_parts.append(f"asset={asset}")

        return MemoryQueryResult(
            entries=entries[:limit],
            total_matches=len(entries),
            query=" & ".join(query_desc_parts) if query_desc_parts else "all",
        )

    def search_similar(
        self,
        content: str,
        limit: int = 10,
    ) -> MemoryQueryResult:
        """Search for entries with content similar to the query string.

        Uses simple keyword overlap for similarity scoring.
        """
        query_tokens = set(content.lower().split())

        scored: list[tuple[MemoryEntry, float]] = []
        for entry in self.records:
            entry_text = entry.record.content.lower()
            entry_tokens = set(entry_text.split())

            if not query_tokens or not entry_tokens:
                continue

            # Jaccard similarity
            intersection = query_tokens & entry_tokens
            union = query_tokens | entry_tokens
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity > 0.05:  # minimum threshold
                scored.append((entry, similarity))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[1], reverse=True)

        entries = [e for e, _ in scored[:limit]]

        return MemoryQueryResult(
            entries=entries,
            total_matches=len(scored),
            query=f"similar_to: {content[:60]}...",
        )

    def update_performance(self, index: int, alpha_performance: float) -> bool:
        """Update the realized alpha performance for a memory entry."""
        if 0 <= index < len(self.records):
            self.records[index].alpha_performance = alpha_performance
            return True
        return False

    def get_best_performing(self, limit: int = 10) -> list[MemoryEntry]:
        """Get entries with the best realized alpha performance."""
        with_perf = [e for e in self.records if e.alpha_performance is not None]
        return sorted(with_perf, key=lambda e: e.alpha_performance or 0, reverse=True)[:limit]

    def get_worst_performing(self, limit: int = 10) -> list[MemoryEntry]:
        """Get entries with the worst realized alpha performance."""
        with_perf = [e for e in self.records if e.alpha_performance is not None]
        return sorted(with_perf, key=lambda e: e.alpha_performance or 0)[:limit]

    def get_stats(self) -> dict:
        """Get memory statistics."""
        total = len(self.records)
        with_alpha = sum(1 for e in self.records if e.alpha_performance is not None)
        avg_retrieval = (
            sum(e.retrieval_count for e in self.records) / total if total > 0 else 0
        )
        sources = {s: len(indices) for s, indices in self._source_index.items()}
        assets = {a: len(indices) for a, indices in self._asset_index.items()}

        return {
            "total_entries": total,
            "entries_with_performance": with_alpha,
            "avg_retrieval_count": round(avg_retrieval, 2),
            "unique_sources": len(sources),
            "unique_assets": len(assets),
            "top_sources": sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_assets": sorted(assets.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    @property
    def entry_count(self) -> int:
        return len(self.records)

    def clear(self) -> None:
        self.records.clear()
        self._source_index.clear()
        self._asset_index.clear()
        self._tag_index.clear()
