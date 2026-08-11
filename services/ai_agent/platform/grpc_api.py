"""Platform gRPC API — high-performance gRPC service for the AI Platform.

Provides gRPC service definitions and server implementation for AI platform
operations. gRPC is used for high-throughput, low-latency internal service
communication and agent-to-agent messaging.

Service methods:
    - Chat: bidirectional streaming chat
    - RunAgent: execute an agent task
    - SubmitWorkflow: submit a workflow DAG
    - StreamEvents: server-side streaming events
    - GetStatus: platform health check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class gRPCServiceMethod:
    """Definition of a gRPC service method."""
    name: str
    request_type: str
    response_type: str
    streaming: str = "unary"  # unary, server_stream, client_stream, bidi
    description: str = ""


@dataclass
class gRPCService:
    """Definition of a gRPC service."""
    service_name: str
    package: str = "icyquant.ai.v1"
    methods: List[gRPCServiceMethod] = field(default_factory=list)


class PlatformgRPCAPI:
    """High-performance gRPC API for the AI Platform.

    Provides gRPC endpoints for high-throughput internal communication
    between AI services and platform components.

    Usage:
        api = PlatformgRPCAPI()
        await api.initialize()
        api.register_service(gRPCService(service_name="AIService", methods=[...]))
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 50051) -> None:
        self._host = host
        self._port = port
        self._services: Dict[str, gRPCService] = {}
        self._handlers: Dict[str, Callable] = {}
        self._total_calls: int = 0
        self._total_errors: int = 0
        self._initialized: bool = False
        logger.info("PlatformgRPCAPI created (host=%s, port=%d)", host, port)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._register_builtin_services()
        self._initialized = True
        logger.info("PlatformgRPCAPI initialized with %d services", len(self._services))

    async def shutdown(self) -> None:
        self._services.clear()
        self._handlers.clear()
        self._initialized = False
        logger.info("PlatformgRPCAPI shutdown complete")

    def _register_builtin_services(self) -> None:
        """Register standard gRPC services."""
        ai_service = gRPCService(
            service_name="AIService",
            package="icyquant.ai.v1",
            methods=[
                gRPCServiceMethod(name="Chat", request_type="ChatRequest", response_type="ChatResponse", streaming="bidi", description="Bidirectional streaming chat"),
                gRPCServiceMethod(name="RunAgent", request_type="RunAgentRequest", response_type="RunAgentResponse", description="Execute agent task"),
                gRPCServiceMethod(name="SubmitWorkflow", request_type="WorkflowRequest", response_type="WorkflowResponse", description="Submit workflow DAG"),
                gRPCServiceMethod(name="StreamEvents", request_type="StreamRequest", response_type="Event", streaming="server_stream", description="Server streaming events"),
                gRPCServiceMethod(name="GetStatus", request_type="StatusRequest", response_type="StatusResponse", description="Platform health check"),
            ],
        )
        self._services[ai_service.service_name] = ai_service

    def register_service(self, service: gRPCService) -> None:
        """Register a gRPC service."""
        self._services[service.service_name] = service
        logger.info("PlatformgRPCAPI: registered service %s (%d methods)", service.service_name, len(service.methods))

    def register_handler(self, service_method: str, handler_fn: Callable) -> None:
        """Register a handler for a service method."""
        self._handlers[service_method] = handler_fn

    async def handle_call(self, service: str, method: str, request: Any) -> Any:
        """Handle an incoming gRPC call."""
        self._total_calls += 1
        key = f"{service}/{method}"

        handler = self._handlers.get(key)
        if not handler:
            self._total_errors += 1
            raise NotImplementedError(f"gRPC handler not found: {key}")

        try:
            return await handler(request)
        except Exception as e:
            self._total_errors += 1
            logger.error("PlatformgRPCAPI: error in %s: %s", key, e)
            raise

    def list_services(self) -> List[Dict[str, Any]]:
        """List all registered services."""
        return [
            {
                "service": s.service_name,
                "package": s.package,
                "methods": [{"name": m.name, "streaming": m.streaming, "description": m.description} for m in s.methods],
            }
            for s in self._services.values()
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "host": self._host,
            "port": self._port,
            "services": len(self._services),
            "handlers": len(self._handlers),
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
        }
