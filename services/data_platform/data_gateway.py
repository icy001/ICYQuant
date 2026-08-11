"""
ICYQuant Unified Data Gateway.

Commit 16 Part 1.5 — The single entry point for all data operations.
All data access (subscribe, query, replay, publish) flows through
the Data Gateway, which delegates to the orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class GatewayMode(str, Enum):
    """Data gateway operational mode."""
    LIVE = "live"
    REPLAY = "replay"
    HYBRID = "hybrid"


@dataclass
class SubscribeRequest:
    """Request to subscribe to a real-time data stream."""
    dataset_id: str = ""
    instruments: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    batch_size: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryRequest:
    """Request to query historical data."""
    dataset_id: str = ""
    instruments: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    as_of: Optional[datetime] = None
    filters: dict[str, Any] = field(default_factory=dict)
    limit: int = 1000
    offset: int = 0
    order_by: str = "timestamp"
    descending: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayRequest:
    """Request to replay historical data as a simulated live feed."""
    dataset_id: str = ""
    instruments: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speed_multiplier: float = 1.0
    loop: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishRequest:
    """Request to publish data to the platform."""
    dataset_id: str = ""
    data: list[dict[str, Any]] = field(default_factory=list)
    producer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataResponse:
    """Unified response from the data gateway."""
    request_id: str = ""
    dataset_id: str = ""
    data: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    latency_ms: float = 0.0
    served_from: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DataGateway:
    """Unified Data Gateway — single entry point for all data operations.

    All platform data access flows through this gateway:
      - subscribe(): real-time streaming data
      - query(): historical data queries (supports time-travel)
      - replay(): historical replay as simulated live
      - publish(): ingest data into the platform
    """

    def __init__(
        self,
        orchestrator: Any = None,
        pipeline: Any = None,
        sdk: Any = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._pipeline = pipeline
        self._sdk = sdk
        self._mode = GatewayMode.LIVE
        self._request_counter = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("DataGateway started in %s mode", self._mode.value)

    async def stop(self) -> None:
        logger.info("DataGateway stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def subscribe(self, request: SubscribeRequest) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a real-time data stream.

        Returns an async iterator yielding data events as they arrive.
        """
        request_id = await self._next_request_id()
        logger.debug("Subscribe request %s: dataset=%s instruments=%s",
                     request_id, request.dataset_id, request.instruments)

        if self._orchestrator:
            async for event in self._orchestrator.subscribe(request):
                yield event
        else:
            # Direct pipeline fallback
            if self._pipeline:
                async for event in self._pipeline.subscribe_stream(request):
                    yield event

    async def query(self, request: QueryRequest) -> DataResponse:
        """Query historical data with optional time-travel.

        Supports point-in-time queries via the as_of parameter.
        """
        start = datetime.now(timezone.utc)
        request_id = await self._next_request_id()
        logger.debug("Query request %s: dataset=%s limit=%d",
                     request_id, request.dataset_id, request.limit)

        if self._orchestrator:
            response = await self._orchestrator.query(request)
        elif self._pipeline:
            response = await self._pipeline.query(request)
        else:
            response = DataResponse(request_id=request_id, dataset_id=request.dataset_id)

        response.request_id = request_id
        response.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return response

    async def replay(self, request: ReplayRequest) -> AsyncIterator[dict[str, Any]]:
        """Replay historical data as a simulated real-time feed.

        The replay runs at the specified speed multiplier, emitting
        events with simulated timestamps.
        """
        request_id = await self._next_request_id()
        logger.info("Replay request %s: dataset=%s speed=%sx",
                    request_id, request.dataset_id, request.speed_multiplier)

        if self._orchestrator:
            async for event in self._orchestrator.replay(request):
                yield event
        elif self._pipeline:
            async for event in self._pipeline.replay_stream(request):
                yield event

    async def publish(self, request: PublishRequest) -> DataResponse:
        """Publish/ingest data into the platform."""
        start = datetime.now(timezone.utc)
        request_id = await self._next_request_id()
        logger.debug("Publish request %s: dataset=%s count=%d",
                     request_id, request.dataset_id, len(request.data))

        if self._orchestrator:
            response = await self._orchestrator.publish(request)
        elif self._pipeline:
            response = await self._pipeline.publish(request)
        else:
            response = DataResponse(request_id=request_id, dataset_id=request.dataset_id)

        response.request_id = request_id
        response.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return response

    # ------------------------------------------------------------------
    # Mode Management
    # ------------------------------------------------------------------

    def set_mode(self, mode: GatewayMode) -> None:
        """Set the gateway operational mode."""
        self._mode = mode
        logger.info("DataGateway mode set to %s", mode.value)

    @property
    def mode(self) -> GatewayMode:
        return self._mode

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _next_request_id(self) -> str:
        async with self._lock:
            self._request_counter += 1
            return f"gw-{self._request_counter:08d}"
