"""
Market Data Manager — lifecycle and coordination manager for the
market data normalization subsystem.

Commit 16 Part 1.2
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .market_data_controller import MarketDataController
from .market_data_engine import EngineConfig, EngineState, MarketDataEngine
from .market_data_normalizer import MarketDataNormalizer

logger = logging.getLogger(__name__)


@dataclass
class ManagerConfig:
    manager_id: str = "icyquant-md-manager"
    auto_start: bool = True
    supervision_interval: float = 5.0
    max_restart_attempts: int = 3


class MarketDataManager:
    """
    Lifecycle manager for the Market Data normalization subsystem.

    Supervises engine health, handles restart logic, and provides
    the administrative interface for the normalization pipeline.
    """

    def __init__(self, config: Optional[ManagerConfig] = None) -> None:
        self.config = config or ManagerConfig()
        self._engine: Optional[MarketDataEngine] = None
        self._controller: Optional[MarketDataController] = None
        self._normalizer: Optional[MarketDataNormalizer] = None

        self._supervisor_task: Optional[asyncio.Task[Any]] = None
        self._restart_count: int = 0
        self._shutdown_event = asyncio.Event()

    async def initialize(self, engine_config: Optional[EngineConfig] = None) -> None:
        """Create and wire up all manager-managed components."""
        logger.info("Initializing MarketDataManager [%s]", self.config.manager_id)

        self._engine = MarketDataEngine(engine_config or EngineConfig())
        self._controller = MarketDataController()
        self._normalizer = MarketDataNormalizer()

        await self._engine.initialize()
        await self._controller.initialize(self._engine)
        await self._normalizer.initialize()

        logger.info("MarketDataManager initialized")

    async def start(self) -> None:
        if not self._engine:
            raise RuntimeError("Manager not initialized")
        await self._engine.start()
        await self._controller.start()

        if self.config.auto_start:
            self._supervisor_task = asyncio.create_task(self._supervise())

        logger.info("MarketDataManager started")

    async def stop(self) -> None:
        logger.info("Stopping MarketDataManager")
        self._shutdown_event.set()

        if self._supervisor_task:
            self._supervisor_task.cancel()
            self._supervisor_task = None

        if self._controller:
            await self._controller.stop()
        if self._engine:
            await self._engine.stop()

        logger.info("MarketDataManager stopped")

    async def _supervise(self) -> None:
        """Supervision loop — monitors engine health and auto-restarts."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.supervision_interval)

                if not self._engine:
                    continue

                health = await self._engine.health_check()
                if health.is_unhealthy and self._restart_count < self.config.max_restart_attempts:
                    logger.warning(
                        "Engine unhealthy, restarting (attempt %d/%d)",
                        self._restart_count + 1,
                        self.config.max_restart_attempts,
                    )
                    await self._engine.stop()
                    await self._engine.start()
                    self._restart_count += 1

            except asyncio.CancelledError:
                break

    @property
    def engine(self) -> Optional[MarketDataEngine]:
        return self._engine

    @property
    def controller(self) -> Optional[MarketDataController]:
        return self._controller

    async def status(self) -> dict[str, Any]:
        return {
            "manager_id": self.config.manager_id,
            "engine": await self._engine.status() if self._engine else {},
            "restart_count": self._restart_count,
        }
