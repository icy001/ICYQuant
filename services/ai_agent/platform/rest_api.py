"""Platform REST API — RESTful endpoints for the AI Platform.

Provides HTTP endpoints for all AI platform operations including chat,
agent execution, workflow management, session handling, and evaluation.

Endpoints:
    POST /ai/chat        — Chat with an AI agent
    POST /ai/run         — Run an agent task
    POST /ai/workflow    — Submit a workflow
    POST /ai/agent       — Manage agent lifecycle
    GET  /ai/session     — Get session info
    GET  /ai/history     — Get interaction history
    GET  /ai/evaluation  — Get evaluation results
    GET  /ai/status      — Platform status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HTTPMethod(str, Enum):
    """HTTP methods supported by the REST API."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


@dataclass
class APIEndpoint:
    """Definition of a REST API endpoint."""
    path: str
    method: HTTPMethod
    handler_name: str
    description: str = ""
    auth_required: bool = True
    rate_limit_rpm: int = 60


@dataclass
class APIResponse:
    """Standardized API response."""
    status: str = "ok"
    data: Any = None
    error: Optional[str] = None
    request_id: str = ""
    latency_ms: float = 0.0


class PlatformRESTAPI:
    """RESTful API for the AI Platform.

    Provides HTTP endpoints for all AI operations including chat,
    agent management, workflow submission, and evaluation.

    Usage:
        api = PlatformRESTAPI()
        await api.initialize()
        api.register_endpoint(APIEndpoint(path="/ai/chat", method=HTTPMethod.POST, handler_name="chat"))
        response = await api.handle_request("POST", "/ai/chat", payload)
    """

    def __init__(self, base_path: str = "/ai") -> None:
        self._base_path = base_path
        self._endpoints: Dict[str, APIEndpoint] = {}
        self._handlers: Dict[str, Any] = {}
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._initialized: bool = False
        logger.info("PlatformRESTAPI created (base_path=%s)", base_path)

    async def initialize(self) -> None:
        if self._initialized:
            return
        # Register built-in endpoints
        self._register_builtin_endpoints()
        self._initialized = True
        logger.info("PlatformRESTAPI initialized with %d endpoints", len(self._endpoints))

    async def shutdown(self) -> None:
        self._endpoints.clear()
        self._handlers.clear()
        self._initialized = False
        logger.info("PlatformRESTAPI shutdown complete")

    def _register_builtin_endpoints(self) -> None:
        """Register the standard AI platform endpoints."""
        builtins = [
            APIEndpoint(path="/ai/chat", method=HTTPMethod.POST, handler_name="chat", description="Chat with AI agent"),
            APIEndpoint(path="/ai/run", method=HTTPMethod.POST, handler_name="run", description="Run agent task"),
            APIEndpoint(path="/ai/workflow", method=HTTPMethod.POST, handler_name="workflow", description="Submit workflow"),
            APIEndpoint(path="/ai/agent", method=HTTPMethod.POST, handler_name="agent_manage", description="Manage agent lifecycle"),
            APIEndpoint(path="/ai/agent", method=HTTPMethod.GET, handler_name="agent_list", description="List agents"),
            APIEndpoint(path="/ai/session", method=HTTPMethod.GET, handler_name="session", description="Get session info"),
            APIEndpoint(path="/ai/history", method=HTTPMethod.GET, handler_name="history", description="Get interaction history"),
            APIEndpoint(path="/ai/evaluation", method=HTTPMethod.GET, handler_name="evaluation", description="Get evaluation results"),
            APIEndpoint(path="/ai/status", method=HTTPMethod.GET, handler_name="status", description="Platform status"),
            APIEndpoint(path="/ai/metrics", method=HTTPMethod.GET, handler_name="metrics", description="Platform metrics"),
        ]
        for ep in builtins:
            self._register_endpoint(ep)

    def _register_endpoint(self, endpoint: APIEndpoint) -> None:
        """Register a single endpoint."""
        key = f"{endpoint.method.value}:{endpoint.path}"
        self._endpoints[key] = endpoint

    def register_endpoint(self, endpoint: APIEndpoint) -> None:
        """Register a custom API endpoint."""
        self._register_endpoint(endpoint)
        logger.info("PlatformRESTAPI: registered %s %s", endpoint.method.value, endpoint.path)

    def register_handler(self, handler_name: str, handler_fn: Any) -> None:
        """Register a handler function for an endpoint."""
        self._handlers[handler_name] = handler_fn

    async def handle_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Handle an incoming HTTP request."""
        self._total_requests += 1
        key = f"{method.upper()}:{path}"

        endpoint = self._endpoints.get(key)
        if not endpoint:
            self._total_errors += 1
            return APIResponse(status="error", error=f"Endpoint not found: {method} {path}")

        try:
            handler = self._handlers.get(endpoint.handler_name)
            if handler:
                result = await handler(payload) if payload else await handler()
            else:
                result = {"message": f"Handler {endpoint.handler_name} not yet implemented"}

            return APIResponse(status="ok", data=result)
        except Exception as e:
            self._total_errors += 1
            logger.error("PlatformRESTAPI: error handling %s %s: %s", method, path, e)
            return APIResponse(status="error", error=str(e))

    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List all registered endpoints."""
        return [
            {"path": ep.path, "method": ep.method.value, "description": ep.description, "auth_required": ep.auth_required}
            for ep in self._endpoints.values()
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "base_path": self._base_path,
            "endpoints": len(self._endpoints),
            "handlers": len(self._handlers),
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
        }
