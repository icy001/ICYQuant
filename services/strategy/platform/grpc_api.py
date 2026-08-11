"""
gRPC API — High-performance gRPC endpoints for the Strategy Platform.

Provides strongly-typed gRPC service definitions for strategy
deployment, runtime management, and signal processing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GRPCMethodType(str, Enum):
    """gRPC method types."""
    UNARY = "unary"
    SERVER_STREAMING = "server_streaming"
    CLIENT_STREAMING = "client_streaming"
    BIDI_STREAMING = "bidi_streaming"


@dataclass
class GRPCMethod:
    """Definition of a gRPC service method."""
    name: str
    method_type: GRPCMethodType = GRPCMethodType.UNARY
    handler: Optional[Callable] = None
    description: str = ""


@dataclass
class GRPCService:
    """Definition of a gRPC service."""
    name: str
    package: str = "icyquant.strategy.v1"
    methods: list[GRPCMethod] = field(default_factory=list)


class StrategyGRPCAPI:
    """
    gRPC API for the Strategy Platform.

    Provides high-performance, strongly-typed RPC services for:
    - DeployService: strategy deployment and lifecycle
    - RuntimeService: strategy runtime management
    - SignalService: signal generation and processing
    - StrategyService: strategy catalog and querying

    Usage::

        api = StrategyGRPCAPI(control_plane=cp)
        await api.initialize()
        services = api.list_services()
    """

    def __init__(
        self,
        control_plane: Any = None,
        catalog: Any = None,
    ) -> None:
        self._control_plane = control_plane
        self._catalog = catalog
        self._services: dict[str, GRPCService] = {}
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the gRPC API and register services."""
        self._register_services()
        self._initialized = True
        logger.info("StrategyGRPCAPI initialized.")

    async def stop(self) -> None:
        """Stop the gRPC API."""
        self._initialized = False
        logger.info("StrategyGRPCAPI stopped.")

    # ---- Service Registration ----

    def _register_services(self) -> None:
        """Register all gRPC service definitions."""

        # DeployService
        deploy_service = GRPCService(
            name="DeployService",
            package="icyquant.strategy.v1",
            methods=[
                GRPCMethod(name="DeployStrategy", method_type=GRPCMethodType.UNARY, description="Deploy a strategy version"),
                GRPCMethod(name="RollbackStrategy", method_type=GRPCMethodType.UNARY, description="Rollback a strategy deployment"),
                GRPCMethod(name="GetDeploymentStatus", method_type=GRPCMethodType.UNARY, description="Get deployment status"),
                GRPCMethod(name="WatchDeployment", method_type=GRPCMethodType.SERVER_STREAMING, description="Watch deployment progress"),
            ],
        )

        # RuntimeService
        runtime_service = GRPCService(
            name="RuntimeService",
            package="icyquant.strategy.v1",
            methods=[
                GRPCMethod(name="StartStrategy", method_type=GRPCMethodType.UNARY, description="Start a strategy"),
                GRPCMethod(name="StopStrategy", method_type=GRPCMethodType.UNARY, description="Stop a strategy"),
                GRPCMethod(name="PauseStrategy", method_type=GRPCMethodType.UNARY, description="Pause a strategy"),
                GRPCMethod(name="ResumeStrategy", method_type=GRPCMethodType.UNARY, description="Resume a paused strategy"),
                GRPCMethod(name="GetRuntimeStatus", method_type=GRPCMethodType.UNARY, description="Get runtime status"),
                GRPCMethod(name="WatchRuntime", method_type=GRPCMethodType.SERVER_STREAMING, description="Watch runtime events"),
            ],
        )

        # SignalService
        signal_service = GRPCService(
            name="SignalService",
            package="icyquant.strategy.v1",
            methods=[
                GRPCMethod(name="GenerateSignal", method_type=GRPCMethodType.UNARY, description="Generate a trading signal"),
                GRPCMethod(name="StreamSignals", method_type=GRPCMethodType.SERVER_STREAMING, description="Stream trading signals"),
                GRPCMethod(name="SubmitOrderIntent", method_type=GRPCMethodType.UNARY, description="Submit an order intent"),
            ],
        )

        # StrategyService
        strategy_service = GRPCService(
            name="StrategyService",
            package="icyquant.strategy.v1",
            methods=[
                GRPCMethod(name="RegisterStrategy", method_type=GRPCMethodType.UNARY, description="Register a strategy"),
                GRPCMethod(name="GetStrategy", method_type=GRPCMethodType.UNARY, description="Get strategy details"),
                GRPCMethod(name="ListStrategies", method_type=GRPCMethodType.UNARY, description="List all strategies"),
                GRPCMethod(name="SearchStrategies", method_type=GRPCMethodType.UNARY, description="Search strategies"),
                GRPCMethod(name="WatchStrategyEvents", method_type=GRPCMethodType.SERVER_STREAMING, description="Watch strategy events"),
            ],
        )

        for service in [deploy_service, runtime_service, signal_service, strategy_service]:
            self._services[service.name] = service

    # ---- Service Access ----

    def get_service(self, name: str) -> Optional[GRPCService]:
        """Get a gRPC service definition by name."""
        return self._services.get(name)

    def list_services(self) -> list[GRPCService]:
        """List all registered gRPC services."""
        return list(self._services.values())

    def get_service_descriptor(self, name: str) -> Optional[dict[str, Any]]:
        """Get a service descriptor for code generation."""
        service = self._services.get(name)
        if not service:
            return None
        return {
            "name": service.name,
            "package": service.package,
            "full_name": f"{service.package}.{service.name}",
            "methods": [
                {
                    "name": m.name,
                    "type": m.method_type.value,
                    "description": m.description,
                }
                for m in service.methods
            ],
        }

    async def health_check(self) -> dict[str, Any]:
        """Check gRPC API health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "services": len(self._services),
            "total_methods": sum(len(s.methods) for s in self._services.values()),
        }
