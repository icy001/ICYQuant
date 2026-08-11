"""
Enrichment Engine — real-time event enrichment from external sources
including reference data, market data, and static datasets.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EnrichmentSource(str, Enum):
    REFERENCE_DATA = "reference_data"
    MARKET_DATA = "market_data"
    STATIC = "static"
    CACHE = "cache"
    EXTERNAL_API = "external_api"


class EnrichmentEngine:
    """
    Real-time event enrichment from external data sources.

    Enriches streaming events with additional context from reference
    data, market snapshots, static datasets, and external APIs.

    Usage::

        engine = EnrichmentEngine()
        engine.register_source("symbol_metadata", get_symbol_metadata, EnrichmentSource.REFERENCE_DATA)
        enriched = await engine.enrich(trade_event, ["symbol_metadata"])
    """

    def __init__(self, cache_ttl_ms: int = 60000) -> None:
        self.cache_ttl_ms = cache_ttl_ms
        self._sources: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, tuple[float, Any]] = {}
        self._enrichment_count = 0

    def register_source(
        self,
        name: str,
        resolver: Callable[..., Any],
        source_type: EnrichmentSource = EnrichmentSource.REFERENCE_DATA,
        *,
        cacheable: bool = True,
    ) -> None:
        """Register an enrichment data source."""
        self._sources[name] = {
            "resolver": resolver,
            "type": source_type,
            "cacheable": cacheable,
        }
        logger.debug("Enrichment source registered: %s (%s)", name, source_type.value)

    def unregister_source(self, name: str) -> bool:
        """Unregister an enrichment source."""
        if name in self._sources:
            del self._sources[name]
            return True
        return False

    async def enrich(
        self,
        event: Any,
        source_names: list[str],
        *,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Enrich an event with data from specified sources."""
        self._enrichment_count += 1
        enriched = dict(event) if isinstance(event, dict) else event

        for source_name in source_names:
            source = self._sources.get(source_name)
            if source is None:
                logger.warning("Enrichment source not found: %s", source_name)
                continue

            try:
                # Check cache
                cache_key = f"{source_name}:{hash(str(event))}"
                if source["cacheable"]:
                    cached = self._cache.get(cache_key)
                    if cached:
                        cached_time, cached_value = cached
                        if (time.monotonic() * 1000 - cached_time) < self.cache_ttl_ms:
                            if isinstance(enriched, dict):
                                enriched[source_name] = cached_value
                            continue

                # Resolve
                resolver = source["resolver"]
                if asyncio.iscoroutinefunction(resolver):
                    value = await resolver(event, context)
                elif callable(resolver):
                    value = resolver(event, context)
                else:
                    value = None

                if isinstance(enriched, dict):
                    enriched[source_name] = value

                # Cache
                if source["cacheable"] and value is not None:
                    self._cache[cache_key] = (time.monotonic() * 1000, value)

            except Exception as e:
                logger.error(
                    "Enrichment failed for source %s: %s", source_name, e,
                )

        return enriched

    async def enrich_batch(
        self,
        events: list[Any],
        source_names: list[str],
        *,
        context: Optional[dict[str, Any]] = None,
    ) -> list[Any]:
        """Enrich a batch of events."""
        tasks = [self.enrich(e, source_names, context=context) for e in events]
        return await asyncio.gather(*tasks)

    async def clear_cache(self) -> int:
        """Clear the enrichment cache."""
        count = len(self._cache)
        self._cache.clear()
        return count

    @property
    def enrichment_count(self) -> int:
        return self._enrichment_count

    async def stats(self) -> dict[str, Any]:
        """Get enrichment engine statistics."""
        return {
            "sources": len(self._sources),
            "source_names": list(self._sources.keys()),
            "cache_entries": len(self._cache),
            "total_enrichments": self._enrichment_count,
        }
