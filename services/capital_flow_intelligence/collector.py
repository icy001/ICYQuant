"""Capital Flow Data Collector.

Collects capital flow data from multiple sources including ETF flows,
fund flows, institutional positions, options flow, dark pool, foreign
flows, bond flows, and commodity flows. Provides unified ingestion,
filtering, and aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .record import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    FlowAssetClass,
)


@dataclass
class FlowCollectionResult:
    """Result of a capital flow collection operation.

    Attributes:
        source: The data source collected from.
        records: Collected flow records.
        count: Number of records collected.
        errors: Collection errors encountered.
        duration_ms: Collection duration in milliseconds.
        timestamp: Collection timestamp.
    """

    source: FlowSource
    records: list[CapitalFlowRecord] = field(default_factory=list)
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

    @property
    def net_flow(self) -> float:
        return sum(r.net_flow_value for r in self.records)


class CapitalFlowCollector:
    """Collects capital flow data from multiple sources.

    Provides a unified interface for ingesting flow data from ETFs,
    mutual funds, hedge funds, institutions, options, dark pools,
    foreign investment, bonds, and commodities.

    Attributes:
        sources: Registered data sources with their collector functions.
        records: All collected flow records.
        source_stats: Collection statistics per source.
    """

    def __init__(self) -> None:
        self.sources: dict[FlowSource, Callable[..., list[CapitalFlowRecord]]] = {}
        self.records: list[CapitalFlowRecord] = []
        self.source_stats: dict[FlowSource, dict[str, Any]] = {}

    # --- Source Registration ---

    def register_source(
        self, source: FlowSource, collector_fn: Callable[..., list[CapitalFlowRecord]]
    ) -> None:
        """Register a data source collector function.

        Args:
            source: The flow source to register.
            collector_fn: Function returning a list of CapitalFlowRecords.
        """
        self.sources[source] = collector_fn
        self.source_stats[source] = {"calls": 0, "records": 0, "errors": 0}

    def unregister_source(self, source: FlowSource) -> None:
        """Remove a registered data source."""
        self.sources.pop(source, None)
        self.source_stats.pop(source, None)

    # --- Collection ---

    def collect(self, asset: str, source: FlowSource | None = None, **kwargs: Any) -> FlowCollectionResult | dict[str, Any]:
        """Collect capital flow data for an asset.

        Args:
            asset: Asset identifier to collect data for.
            source: Optional specific source; if None, uses first registered.
            **kwargs: Additional arguments for the collector function.

        Returns:
            FlowCollectionResult if source specified, else a dict with asset info.
        """
        if source is None:
            return {"asset": asset, "sources": [s.value for s in self.sources]}

        start = datetime.now()
        errors: list[str] = []
        records: list[CapitalFlowRecord] = []

        collector = self.sources.get(source)
        if collector is None:
            errors.append(f"Source '{source.value}' is not registered")
        else:
            try:
                records = collector(asset=asset, **kwargs)
                self.records.extend(records)
                self.source_stats.setdefault(source, {"calls": 0, "records": 0, "errors": 0})
                self.source_stats[source]["calls"] += 1
                self.source_stats[source]["records"] += len(records)
            except Exception as e:
                errors.append(f"Collection failed for {source.value}: {e}")
                self.source_stats.setdefault(source, {"calls": 0, "records": 0, "errors": 0})
                self.source_stats[source]["errors"] += 1

        duration = (datetime.now() - start).total_seconds() * 1000
        return FlowCollectionResult(
            source=source,
            records=records,
            count=len(records),
            errors=errors,
            duration_ms=duration,
        )

    def collect_all(self, asset: str, **kwargs: Any) -> list[FlowCollectionResult]:
        """Collect from all registered sources for an asset.

        Args:
            asset: Asset identifier.
            **kwargs: Additional arguments.

        Returns:
            List of FlowCollectionResult, one per registered source.
        """
        results: list[FlowCollectionResult] = []
        for source_key in self.sources:
            result = self.collect(asset=asset, source=source_key, **kwargs)
            if isinstance(result, FlowCollectionResult):
                results.append(result)
        return results

    # --- Filtering ---

    def get_by_source(self, source: FlowSource) -> list[CapitalFlowRecord]:
        """Get all records from a specific source."""
        return [r for r in self.records if r.source == source]

    def get_by_asset(self, asset: str) -> list[CapitalFlowRecord]:
        """Get all records for a specific asset."""
        return [r for r in self.records if r.asset == asset]

    def get_by_asset_class(self, asset_class: FlowAssetClass) -> list[CapitalFlowRecord]:
        """Get all records for an asset class."""
        return [r for r in self.records if r.asset_class == asset_class]

    def get_significant(self) -> list[CapitalFlowRecord]:
        """Get significant flow records."""
        return [r for r in self.records if r.is_significant]

    def get_inflows(self) -> list[CapitalFlowRecord]:
        """Get all inflow records."""
        return [r for r in self.records if r.is_inflow]

    def get_outflows(self) -> list[CapitalFlowRecord]:
        """Get all outflow records."""
        return [r for r in self.records if r.is_outflow]

    def get_strong_flows(self) -> list[CapitalFlowRecord]:
        """Get strong flow records."""
        return [r for r in self.records if r.is_strong]

    # --- Aggregation ---

    def net_flow_by_asset(self, asset: str, source: FlowSource | None = None) -> float:
        """Compute net capital flow for an asset.

        Args:
            asset: Asset identifier.
            source: Optional source filter.

        Returns:
            Net flow value (positive=net inflow).
        """
        records = self.get_by_asset(asset)
        if source:
            records = [r for r in records if r.source == source]
        return sum(r.net_flow_value for r in records) if records else 0.0

    def net_flow_by_asset_class(self, asset_class: FlowAssetClass) -> float:
        """Compute net capital flow for an asset class."""
        records = self.get_by_asset_class(asset_class)
        return sum(r.net_flow_value for r in records) if records else 0.0

    def aggregate_direction(
        self, asset: str | None = None, source: FlowSource | None = None
    ) -> FlowDirection:
        """Determine aggregate flow direction.

        Args:
            asset: Optional asset filter.
            source: Optional source filter.

        Returns:
            Aggregate FlowDirection.
        """
        net = self.net_flow_by_asset(asset, source) if asset else sum(
            r.net_flow_value for r in self.records
        )
        if net > 1.0:
            return FlowDirection.STRONG_INFLOW
        elif net > 0.1:
            return FlowDirection.INFLOW
        elif net < -1.0:
            return FlowDirection.STRONG_OUTFLOW
        elif net < -0.1:
            return FlowDirection.OUTFLOW
        return FlowDirection.NEUTRAL

    # --- Lifecycle ---

    def clear(self) -> None:
        """Clear all collected records and reset statistics."""
        self.records.clear()
        for src in self.source_stats:
            self.source_stats[src] = {"calls": 0, "records": 0, "errors": 0}

    @property
    def total_records(self) -> int:
        return len(self.records)

    @property
    def registered_sources(self) -> list[FlowSource]:
        return list(self.sources.keys())
