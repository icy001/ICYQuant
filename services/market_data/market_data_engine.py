"""
Market Data Engine — central orchestrator for the entire market data
normalization pipeline.

Coordinates ingestion, normalization, validation, quality checking,
and publishing of canonical market data to downstream consumers.

Commit 16 Part 1.2
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from .canonical_model import CanonicalMarketData, DataQuality, MarketDataEventType
from .diagnostics import MarketDataDiagnostics
from .health import MarketDataHealthChecker, HealthStatus
from .market_data_cache import MarketDataCache
from .market_data_pipeline import MarketDataPipeline, PipelineConfig
from .market_data_runtime import MarketDataRuntime, MarketDataRuntimeConfig, MarketDataRuntimeStatus
from .metrics import MarketDataMetrics

logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class EngineConfig:
    engine_id: str = "icyquant-market-data"
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    runtime: MarketDataRuntimeConfig = field(default_factory=MarketDataRuntimeConfig)

    metrics_enabled: bool = True
    telemetry_enabled: bool = True
    cache_enabled: bool = True
    health_check_interval: float = 10.0

    max_queue_size: int = 100_000
    consumer_count: int = 4
    graceful_shutdown_timeout: float = 30.0


class MarketDataEngine:
    """
    Central orchestrator for the Market Data Normalization Engine.

    Coordinates the full pipeline: ingest → normalize → validate →
    quality-check → cache → publish.

    Usage::

        engine = MarketDataEngine()
        await engine.initialize(config)
        await engine.start()

        async for event in engine.ingest(raw_data):
            await engine.publish(event)

        await engine.stop()
    """

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self._state = EngineState.CREATED

        self._pipeline: Optional[MarketDataPipeline] = None
        self._runtime: Optional[MarketDataRuntime] = None
        self._cache: Optional[MarketDataCache] = None
        self._metrics: Optional[MarketDataMetrics] = None
        self._diagnostics: Optional[MarketDataDiagnostics] = None
        self._health: Optional[MarketDataHealthChecker] = None

        self._subscribers: list[asyncio.Queue[CanonicalMarketData]] = []
        self._event_counter: int = 0
        self._started_at: Optional[datetime] = None

    # ── Lifecycle ──────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all engine components."""
        self._state = EngineState.INITIALIZING
        logger.info("Initializing Market Data Engine [%s]", self.config.engine_id)

        self._pipeline = MarketDataPipeline(self.config.pipeline)
        self._runtime = MarketDataRuntime(self.config.runtime)
        self._cache = MarketDataCache() if self.config.cache_enabled else None
        self._metrics = MarketDataMetrics() if self.config.metrics_enabled else None
        self._diagnostics = MarketDataDiagnostics()
        self._health = MarketDataHealthChecker()

        await self._pipeline.initialize()
        if self._cache:
            await self._cache.initialize()
        if self._metrics:
            await self._metrics.initialize()
        await self._health.initialize()

        self._state = EngineState.STOPPED
        logger.info("Market Data Engine initialized")

    async def start(self) -> None:
        """Start the engine — begin processing market data."""
        self._state = EngineState.RUNNING
        self._started_at = datetime.now(timezone.utc)
        logger.info("Market Data Engine started [%s]", self.config.engine_id)

        if self._runtime:
            await self._runtime.start()
        if self._health:
            self._health.start_monitoring(interval=self.config.health_check_interval)

    async def stop(self) -> None:
        """Gracefully stop the engine."""
        self._state = EngineState.STOPPING
        logger.info("Stopping Market Data Engine")

        if self._runtime:
            await self._runtime.stop()
        if self._health:
            await self._health.stop_monitoring()

        # Drain subscribers
        for queue in self._subscribers:
            await queue.put(None)  # Sentinel

        self._state = EngineState.STOPPED
        logger.info("Market Data Engine stopped (events processed: %d)", self._event_counter)

    async def pause(self) -> None:
        self._state = EngineState.PAUSED
        logger.info("Market Data Engine paused")

    async def resume(self) -> None:
        self._state = EngineState.RUNNING
        logger.info("Market Data Engine resumed")

    # ── Data Ingestion ─────────────────────────────

    async def ingest(self, raw_data: dict[str, Any]) -> Optional[CanonicalMarketData]:
        """
        Ingest a raw market data event and run through the full pipeline.

        Returns the normalized canonical event, or None if rejected.
        """
        if self._state != EngineState.RUNNING:
            logger.warning("Engine not running, skipping ingest")
            return None

        if not self._pipeline:
            logger.error("Pipeline not initialized")
            return None

        try:
            result = await self._pipeline.process(raw_data)
            if result:
                self._event_counter += 1
                if self._metrics:
                    self._metrics.record_event(result)
                if self._cache and self.config.cache_enabled:
                    await self._cache.put(result)
            return result
        except Exception:
            logger.exception("Pipeline processing failed for event")
            if self._metrics:
                self._metrics.increment_pipeline_errors()
            return None

    async def ingest_batch(self, batch: list[dict[str, Any]]) -> list[CanonicalMarketData]:
        """Process a batch of raw events concurrently."""
        tasks = [self.ingest(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, CanonicalMarketData)]

    async def ingest_stream(self, stream: AsyncIterator[dict[str, Any]]) -> AsyncIterator[CanonicalMarketData]:
        """Async generator that yields canonical events from a raw stream."""
        async for raw in stream:
            result = await self.ingest(raw)
            if result:
                yield result

    # ── Publishing ─────────────────────────────────

    async def publish(self, event: CanonicalMarketData) -> None:
        """Publish a canonical event to all subscribers."""
        if event.quality in (DataQuality.REJECTED, DataQuality.POOR):
            logger.debug("Skipping publish for %s quality event: %s", event.quality.value, event.event_id)
            return
        for queue in self._subscribers:
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue[CanonicalMarketData]:
        """Create a new subscriber queue for canonical events."""
        queue: asyncio.Queue[CanonicalMarketData] = asyncio.Queue(maxsize=10_000)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[CanonicalMarketData]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    # ── Status ─────────────────────────────────────

    async def status(self) -> dict[str, Any]:
        return {
            "engine_id": self.config.engine_id,
            "state": self._state.value,
            "events_processed": self._event_counter,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "pipeline": await self._pipeline.status() if self._pipeline else {},
            "subscribers": len(self._subscribers),
            "health": await self._health.check() if self._health else {},
        }

    async def health_check(self) -> HealthStatus:
        if not self._health:
            return HealthStatus.UNKNOWN
        return await self._health.check()
