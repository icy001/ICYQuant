"""
Protocol Factory — Factory for creating protocol instances based on
exchange capabilities, configuration, and endpoint auto-detection.

Automatically selects the best protocol for a given exchange and
use case (market data, trading, account management).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .protocol_manager import Protocol, ProtocolManager
from .websocket_protocol import WebSocketProtocol
from .rest_protocol import RESTProtocol
from .grpc_protocol import GRPCProtocol
from .tcp_protocol import TCPProtocol
from .udp_protocol import UDPProtocol
from .multicast_protocol import MulticastProtocol

logger = logging.getLogger(__name__)


# Protocol priority for auto-selection by use case
DEFAULT_PRIORITY = {
    "market_data": ["websocket", "multicast", "udp", "rest", "grpc"],
    "trading": ["rest", "websocket", "grpc", "tcp"],
    "account": ["rest", "grpc", "websocket"],
    "reference_data": ["rest", "grpc"],
}


class ProtocolFactory:
    """
    Factory for creating protocol instances.

    Registers all standard protocols with the ProtocolManager and
    provides factory methods with auto-detection of the best protocol
    for a given use case.

    Usage::

        factory = ProtocolFactory()
        await factory.initialize()

        # Auto-detect best protocol for market data
        ws = await factory.create_for_use_case("market_data")
        await ws.connect("wss://stream.binance.com/ws")

        # Explicit protocol selection
        rest = await factory.create("rest", base_url="https://api.binance.com")
    """

    def __init__(self, manager: Optional[ProtocolManager] = None) -> None:
        self._manager = manager or ProtocolManager()
        self._priority: dict[str, list[str]] = dict(DEFAULT_PRIORITY)

    async def initialize(self) -> None:
        """Initialize factory and register all standard protocols."""
        await self._manager.initialize()
        self._register_defaults()
        logger.info("ProtocolFactory initialized with %d protocols.", len(self._manager.list_protocols()))

    def set_priority(self, use_case: str, protocols: list[str]) -> None:
        """Override the protocol priority for a use case."""
        self._priority[use_case] = protocols

    # ---- Factory Methods ----

    async def create(
        self, protocol_name: str, instance_id: Optional[str] = None, **kwargs: Any
    ) -> Optional[Protocol]:
        """Create a protocol instance by name."""
        return await self._manager.create(protocol_name, instance_id, **kwargs)

    async def create_for_use_case(
        self, use_case: str, **kwargs: Any
    ) -> Optional[Protocol]:
        """
        Create the best protocol instance for a given use case.

        Uses the priority list for the use case and selects the first
        registered protocol. Falls back to REST as universal default.
        """
        priorities = self._priority.get(use_case, ["rest"])
        registered = set(self._manager.list_protocols())

        for protocol_name in priorities:
            if protocol_name in registered:
                instance = await self._manager.create(protocol_name, **kwargs)
                if instance:
                    logger.info(
                        "Created %s protocol for use case '%s'",
                        protocol_name, use_case,
                    )
                    return instance

        # Fallback to REST
        if "rest" in registered:
            logger.warning("No preferred protocol for '%s', falling back to REST", use_case)
            return await self._manager.create("rest", **kwargs)

        logger.error("No protocol available for use case '%s'", use_case)
        return None

    async def create_websocket(self, **kwargs: Any) -> Optional[WebSocketProtocol]:
        """Create a WebSocket protocol instance."""
        instance = await self._manager.create("websocket", **kwargs)
        return instance if isinstance(instance, WebSocketProtocol) else None

    async def create_rest(self, **kwargs: Any) -> Optional[RESTProtocol]:
        """Create a REST protocol instance."""
        instance = await self._manager.create("rest", **kwargs)
        return instance if isinstance(instance, RESTProtocol) else None

    async def create_grpc(self, **kwargs: Any) -> Optional[GRPCProtocol]:
        """Create a gRPC protocol instance."""
        instance = await self._manager.create("grpc", **kwargs)
        return instance if isinstance(instance, GRPCProtocol) else None

    async def create_tcp(self, **kwargs: Any) -> Optional[TCPProtocol]:
        """Create a TCP protocol instance."""
        instance = await self._manager.create("tcp", **kwargs)
        return instance if isinstance(instance, TCPProtocol) else None

    async def create_udp(self, **kwargs: Any) -> Optional[UDPProtocol]:
        """Create a UDP protocol instance."""
        instance = await self._manager.create("udp", **kwargs)
        return instance if isinstance(instance, UDPProtocol) else None

    async def create_multicast(self, **kwargs: Any) -> Optional[MulticastProtocol]:
        """Create a Multicast protocol instance."""
        instance = await self._manager.create("multicast", **kwargs)
        return instance if isinstance(instance, MulticastProtocol) else None

    # ---- Properties ----

    @property
    def manager(self) -> ProtocolManager:
        return self._manager

    def list_use_cases(self) -> list[str]:
        """List all configured use cases."""
        return list(self._priority.keys())

    def get_priority(self, use_case: str) -> list[str]:
        """Get protocol priority for a use case."""
        return self._priority.get(use_case, [])

    # ---- Internal ----

    def _register_defaults(self) -> None:
        """Register all standard protocol implementations."""
        self._manager.register("websocket", WebSocketProtocol)
        self._manager.register("rest", RESTProtocol)
        self._manager.register("grpc", GRPCProtocol)
        self._manager.register("tcp", TCPProtocol)
        self._manager.register("udp", UDPProtocol)
        self._manager.register("multicast", MulticastProtocol)
