"""Sentiment Data Collector.

Collects sentiment data from multiple heterogeneous sources including news,
social media, forums, analyst reports, options flow, and market data.
Provides unified ingestion, filtering, and aggregation capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .record import SentimentRecord, SentimentSource, SentimentLabel


@dataclass
class CollectionResult:
    """Result of a collection operation.

    Attributes:
        source: The data source collected from.
        records: Collected sentiment records.
        count: Number of records collected.
        errors: Collection errors encountered.
        duration_ms: Collection duration in milliseconds.
        timestamp: Collection timestamp.
    """

    source: SentimentSource
    records: list[SentimentRecord] = field(default_factory=list)
    count: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_data(self) -> bool:
        return len(self.records) > 0


class SentimentCollector:
    """Collects sentiment data from multiple sources.

    Provides a unified interface for ingesting sentiment data from news,
    social media, forums, analyst reports, options flow, and market data.

    Attributes:
        sources: Registered data sources with their collector functions.
        records: All collected sentiment records.
        source_stats: Collection statistics per source.
    """

    def __init__(self) -> None:
        self.sources: dict[SentimentSource, Callable[..., list[SentimentRecord]]] = {}
        self.records: list[SentimentRecord] = []
        self.source_stats: dict[SentimentSource, dict[str, Any]] = {}

    # --- Source Registration ---

    def register_source(
        self, source: SentimentSource, collector_fn: Callable[..., list[SentimentRecord]]
    ) -> None:
        """Register a data source collector function.

        Args:
            source: The sentiment source to register.
            collector_fn: Function that returns a list of SentimentRecords.
        """
        self.sources[source] = collector_fn
        self.source_stats[source] = {"calls": 0, "records": 0, "errors": 0}

    def unregister_source(self, source: SentimentSource) -> None:
        """Remove a registered data source.

        Args:
            source: The sentiment source to remove.
        """
        self.sources.pop(source, None)
        self.source_stats.pop(source, None)

    # --- Collection ---

    def collect(self, source: SentimentSource, **kwargs: Any) -> CollectionResult:
        """Collect sentiment data from a specific source.

        Args:
            source: The data source to collect from.
            **kwargs: Additional arguments passed to the collector function.

        Returns:
            CollectionResult with collected records and metadata.
        """
        start = datetime.now()
        errors: list[str] = []
        records: list[SentimentRecord] = []

        collector = self.sources.get(source)
        if collector is None:
            errors.append(f"Source '{source.value}' is not registered")
        else:
            try:
                records = collector(**kwargs)
                self.records.extend(records)
                self.source_stats.setdefault(source, {"calls": 0, "records": 0, "errors": 0})
                self.source_stats[source]["calls"] += 1
                self.source_stats[source]["records"] += len(records)
            except Exception as e:
                errors.append(f"Collection failed for {source.value}: {e}")
                self.source_stats.setdefault(source, {"calls": 0, "records": 0, "errors": 0})
                self.source_stats[source]["errors"] += 1

        duration = (datetime.now() - start).total_seconds() * 1000
        return CollectionResult(
            source=source,
            records=records,
            count=len(records),
            errors=errors,
            duration_ms=duration,
        )

    def collect_all(self, **kwargs: Any) -> list[CollectionResult]:
        """Collect sentiment data from all registered sources.

        Args:
            **kwargs: Additional arguments passed to each collector function.

        Returns:
            List of CollectionResult, one per registered source.
        """
        results: list[CollectionResult] = []
        for source in self.sources:
            result = self.collect(source, **kwargs)
            results.append(result)
        return results

    # --- Filtering ---

    def get_by_source(self, source: SentimentSource) -> list[SentimentRecord]:
        """Get all records from a specific source.

        Args:
            source: The sentiment source to filter by.

        Returns:
            Filtered list of SentimentRecords.
        """
        return [r for r in self.records if r.source == source]

    def get_by_symbol(self, symbol: str) -> list[SentimentRecord]:
        """Get all records for a specific trading symbol.

        Args:
            symbol: Trading symbol to filter by.

        Returns:
            Filtered list of SentimentRecords.
        """
        return [r for r in self.records if r.symbol == symbol]

    def get_by_entity(self, entity: str) -> list[SentimentRecord]:
        """Get all records mentioning a specific entity.

        Args:
            entity: Entity name to filter by.

        Returns:
            Filtered list of SentimentRecords.
        """
        return [r for r in self.records if r.entity == entity]

    def get_reliable(self, min_confidence: float = 0.6) -> list[SentimentRecord]:
        """Get records above a confidence threshold.

        Args:
            min_confidence: Minimum confidence level.

        Returns:
            Filtered list of reliable SentimentRecords.
        """
        return [r for r in self.records if r.confidence >= min_confidence]

    def get_extreme(self) -> list[SentimentRecord]:
        """Get records with extreme sentiment scores (abs >= 0.8).

        Returns:
            Filtered list of extreme SentimentRecords.
        """
        return [r for r in self.records if r.is_extreme]

    def get_positive(self) -> list[SentimentRecord]:
        """Get records with positive sentiment.

        Returns:
            Filtered list of positive SentimentRecords.
        """
        return [r for r in self.records if r.is_positive]

    def get_negative(self) -> list[SentimentRecord]:
        """Get records with negative sentiment.

        Returns:
            Filtered list of negative SentimentRecords.
        """
        return [r for r in self.records if r.is_negative]

    # --- Aggregation ---

    def aggregate_score(
        self, source: SentimentSource | None = None, symbol: str | None = None
    ) -> float:
        """Compute average sentiment score, optionally filtered.

        Args:
            source: Optional source filter.
            symbol: Optional symbol filter.

        Returns:
            Average sentiment score, or 0.0 if no records.
        """
        records = self.records
        if source is not None:
            records = [r for r in records if r.source == source]
        if symbol is not None:
            records = [r for r in records if r.symbol == symbol]

        if not records:
            return 0.0
        return sum(r.score for r in records) / len(records)

    def aggregate_strength(
        self, source: SentimentSource | None = None, symbol: str | None = None
    ) -> float:
        """Compute average composite strength (score * confidence).

        Args:
            source: Optional source filter.
            symbol: Optional symbol filter.

        Returns:
            Average strength, or 0.0 if no records.
        """
        records = self.records
        if source is not None:
            records = [r for r in records if r.source == source]
        if symbol is not None:
            records = [r for r in records if r.symbol == symbol]

        if not records:
            return 0.0
        return sum(r.strength for r in records) / len(records)

    def count_by_label(self) -> dict[SentimentLabel, int]:
        """Count records grouped by sentiment label.

        Returns:
            Dict mapping label to count.
        """
        counts: dict[SentimentLabel, int] = {label: 0 for label in SentimentLabel}
        for r in self.records:
            counts[r.label] = counts.get(r.label, 0) + 1
        return counts

    # --- Lifecycle ---

    def clear(self) -> None:
        """Clear all collected records and reset statistics."""
        self.records.clear()
        for source in self.source_stats:
            self.source_stats[source] = {"calls": 0, "records": 0, "errors": 0}

    @property
    def total_records(self) -> int:
        return len(self.records)

    @property
    def registered_sources(self) -> list[SentimentSource]:
        return list(self.sources.keys())
