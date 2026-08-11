"""
Market Data Controller — command-and-control interface for the
Market Data Engine and normalization pipeline.

Commit 16 Part 1.2
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from .market_data_engine import EngineState, MarketDataEngine

logger = logging.getLogger(__name__)


class ControllerState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class ControllerConfig:
    controller_id: str = "icyquant-md-controller"
    max_command_queue: int = 1000
    command_timeout: float = 10.0


CommandHandler = Callable[..., Any]


class MarketDataController:
    """
    Command-and-control interface for the Market Data subsystem.

    Provides administrative commands: start/stop/pause/resume the engine,
    reconfigure pipelines, trigger diagnostics, and inspect state.
    """

    def __init__(self, config: Optional[ControllerConfig] = None) -> None:
        self.config = config or ControllerConfig()
        self._state = ControllerState.CREATED
        self._engine: Optional[MarketDataEngine] = None
        self._command_queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self._handlers: dict[str, CommandHandler] = {}
        self._processor_task: Optional[asyncio.Task[Any]] = None

    async def initialize(self, engine: MarketDataEngine) -> None:
        self._engine = engine
        self._register_default_handlers()
        logger.info("MarketDataController initialized [%s]", self.config.controller_id)

    async def start(self) -> None:
        self._state = ControllerState.ACTIVE
        self._processor_task = asyncio.create_task(self._process_commands())
        logger.info("MarketDataController active")

    async def stop(self) -> None:
        self._state = ControllerState.STOPPED
        if self._processor_task:
            self._processor_task.cancel()
        logger.info("MarketDataController stopped")

    # ── Commands ───────────────────────────────────

    async def send_command(self, command: str, **kwargs: Any) -> Any:
        """Send a command and wait for result."""
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        await self._command_queue.put((command, {**kwargs, "_future": future}))
        try:
            return await asyncio.wait_for(future, timeout=self.config.command_timeout)
        except asyncio.TimeoutError:
            return {"error": "command_timeout", "command": command}

    async def _process_commands(self) -> None:
        """Background command processor."""
        while self._state == ControllerState.ACTIVE:
            try:
                command, params = await asyncio.wait_for(
                    self._command_queue.get(), timeout=1.0
                )
                future = params.pop("_future", None)

                handler = self._handlers.get(command)
                if handler:
                    result = await handler(**params)
                else:
                    result = {"error": f"unknown_command: {command}"}

                if future and not future.done():
                    future.set_result(result)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def _register_default_handlers(self) -> None:
        self._handlers["start"] = self._handle_start
        self._handlers["stop"] = self._handle_stop
        self._handlers["pause"] = self._handle_pause
        self._handlers["resume"] = self._handle_resume
        self._handlers["status"] = self._handle_status
        self._handlers["diagnostics"] = self._handle_diagnostics
        self._handlers["reconfigure"] = self._handle_reconfigure

    async def _handle_start(self, **kwargs: Any) -> dict[str, Any]:
        if self._engine:
            await self._engine.start()
            return {"result": "started"}
        return {"error": "no_engine"}

    async def _handle_stop(self, **kwargs: Any) -> dict[str, Any]:
        if self._engine:
            await self._engine.stop()
            return {"result": "stopped"}
        return {"error": "no_engine"}

    async def _handle_pause(self, **kwargs: Any) -> dict[str, Any]:
        if self._engine:
            await self._engine.pause()
            return {"result": "paused"}
        return {"error": "no_engine"}

    async def _handle_resume(self, **kwargs: Any) -> dict[str, Any]:
        if self._engine:
            await self._engine.resume()
            return {"result": "resumed"}
        return {"error": "no_engine"}

    async def _handle_status(self, **kwargs: Any) -> dict[str, Any]:
        if self._engine:
            return await self._engine.status()
        return {"error": "no_engine"}

    async def _handle_diagnostics(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "diagnostics_not_yet_triggered"}

    async def _handle_reconfigure(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "reconfigure_applied", "changes": kwargs}

    @property
    def state(self) -> ControllerState:
        return self._state
