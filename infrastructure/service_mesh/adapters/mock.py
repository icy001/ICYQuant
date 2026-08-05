"""Mock proxy adapter for testing the Service Mesh.

Provides ``MockProxyAdapter`` for testing without real network
connections, supporting configurable responses and failure
injection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockProxyAdapter:
    """Mock proxy adapter for testing.

    Supports configurable responses, simulated latency,
    and failure injection for testing mesh behaviors.
    """

    def __init__(self) -> None:
        self._running = False
        self._responses: Dict[str, Dict[str, Any]] = {}
        self._default_response: Dict[str, Any] = {
            "status": 200,
            "body": {"proxied": True, "adapter": "mock"},
        }
        self._failures: Dict[str, float] = {}
        self._latency_ms: float = 0.0
        self._request_count = 0
        self._request_log: List[Dict[str, Any]] = []

    async def start(self) -> Dict[str, Any]:
        self._running = True
        return {"success": True, "adapter": "mock"}

    async def stop(self) -> Dict[str, Any]:
        self._running = False
        return {"success": True}

    @property
    def is_running(self) -> bool:
        return self._running

    def set_response(
        self,
        path: str,
        response: Dict[str, Any],
    ) -> None:
        """Set a mock response for a path."""
        self._responses[path] = response

    def set_default_response(
        self, response: Dict[str, Any]
    ) -> None:
        self._default_response = response

    def set_failure(
        self, path: str, failure_rate: float = 0.5
    ) -> None:
        """Set failure injection rate for a path."""
        self._failures[path] = failure_rate

    def set_latency(self, latency_ms: float) -> None:
        """Set simulated latency in milliseconds."""
        self._latency_ms = latency_ms

    async def forward(
        self,
        target: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        """Forward a request with mock behavior."""
        self._request_count += 1

        # Log request
        self._request_log.append({
            "target": target,
            "method": method,
            "path": path,
            "timestamp": time.monotonic(),
        })

        # Simulate latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)

        # Check for failure injection
        failure_rate = self._failures.get(path, 0.0)
        if failure_rate > 0:
            import random

            if random.random() < failure_rate:
                return {
                    "status": 500,
                    "body": {
                        "error": "Mock failure injected",
                        "path": path,
                    },
                    "adapter": "mock",
                }

        # Return configured or default response
        response = self._responses.get(
            path, self._default_response
        )
        result = dict(response)
        result["_mock"] = True
        result["_request_count"] = self._request_count
        return result

    def get_request_log(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        return self._request_log[-limit:]

    def clear_request_log(self) -> None:
        self._request_log.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "configured_responses": list(self._responses.keys()),
            "failure_injection": dict(self._failures),
            "latency_ms": self._latency_ms,
            "request_count": self._request_count,
            "logged_requests": len(self._request_log),
        }
