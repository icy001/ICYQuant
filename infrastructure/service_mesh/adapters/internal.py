"""Internal proxy adapter for the Service Mesh.

Provides ``InternalProxyAdapter`` as the default proxy
implementation that runs in-process without external
proxy dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class InternalProxyAdapter:
    """In-process proxy adapter for default mesh operation.

    Routes requests to registered backend handlers without
    requiring an external proxy process.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._request_count = 0
        self._running = False

    async def start(self) -> Dict[str, Any]:
        self._running = True
        logger.info("Internal proxy adapter started.")
        return {"success": True}

    async def stop(self) -> Dict[str, Any]:
        self._running = False
        logger.info("Internal proxy adapter stopped.")
        return {"success": True}

    @property
    def is_running(self) -> bool:
        return self._running

    def register_handler(
        self, path: str, handler: Callable
    ) -> None:
        """Register a request handler for a path prefix."""
        self._handlers[path] = handler

    def add_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    async def forward(
        self,
        target: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        """Forward a request to the appropriate handler."""
        self._request_count += 1

        # Apply middleware
        for mw in self._middleware:
            result = mw(method, path, headers, body)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                return result

        # Find matching handler
        for prefix, handler in self._handlers.items():
            if path.startswith(prefix):
                try:
                    result = handler(
                        method, path, headers, body
                    )
                    if asyncio.iscoroutine(result):
                        result = await result
                    return result
                except Exception as exc:
                    return {
                        "status": 500,
                        "body": {"error": str(exc)},
                    }

        return {
            "status": 200,
            "body": {
                "target": target,
                "method": method,
                "path": path,
                "proxied": True,
                "adapter": "internal",
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "handlers": list(self._handlers.keys()),
            "middleware_count": len(self._middleware),
            "request_count": self._request_count,
        }
