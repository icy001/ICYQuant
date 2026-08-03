"""Application lifecycle hooks."""
from __future__ import annotations
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

async def on_startup() -> None:
    logger.info("Application startup")

async def on_shutdown() -> None:
    logger.info("Application shutdown")

def register_lifespan_hooks(
    app,
    startup_hooks: list[Callable[[], Awaitable[None]]] | None = None,
    shutdown_hooks: list[Callable[[], Awaitable[None]]] | None = None,
) -> None:
    startup_hooks = startup_hooks or []
    shutdown_hooks = shutdown_hooks or []
    app.state.startup_hooks = startup_hooks
    app.state.shutdown_hooks = shutdown_hooks