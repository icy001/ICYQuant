"""
UDP Protocol — UDP transport implementation for low-latency
market data distribution with multicast group support.

UDP is ideal for high-throughput, low-latency market data feeds
where occasional packet loss is acceptable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .protocol_manager import Protocol

logger = logging.getLogger(__name__)


class UDPProtocol(Protocol):
    """
    UDP protocol implementation for exchange connectivity.

    Provides connectionless, low-latency datagram communication
    ideal for high-throughput market data feeds.

    Usage::

        udp = UDPProtocol()
        await udp.connect("udp://market-data.example.com:9000")
        await udp.send(b"subscribe BTCUSDT")
        data = await udp.receive()
        await udp.close()
    """

    def __init__(
        self,
        buffer_size: int = 65507,
        read_timeout: float = 1.0,
    ) -> None:
        super().__init__()
        self.buffer_size = buffer_size
        self.read_timeout = read_timeout
        self._endpoint: str = ""
        self._connected: bool = False
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[asyncio.DatagramProtocol] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._packets_sent: int = 0
        self._packets_received: int = 0
        self._packets_lost: int = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def protocol_name(self) -> str:
        return "udp"

    async def connect(self, endpoint: str, **kwargs: Any) -> bool:
        """Create a UDP endpoint."""
        self._endpoint = endpoint
        host, port = self._parse_endpoint(endpoint)
        try:
            logger.info("Opening UDP endpoint: %s:%d", host, port)
            loop = asyncio.get_event_loop()
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                lambda: _UDPQueueProtocol(self._queue),
                remote_addr=(host, port),
            )
            self._connected = True
            logger.info("UDP endpoint opened: %s:%d", host, port)
            return True
        except Exception:
            logger.exception("UDP connection failed: %s:%d", host, port)
            return False

    async def send(self, data: Any) -> bool:
        """Send data over UDP."""
        if not self._connected or not self._transport:
            logger.error("Cannot send: UDP not connected")
            return False
        try:
            payload = data if isinstance(data, bytes) else str(data).encode()
            self._transport.sendto(payload)
            self._packets_sent += 1
            return True
        except Exception:
            logger.exception("UDP send error")
            return False

    async def receive(self, timeout: float = 0) -> Optional[bytes]:
        """Receive data over UDP."""
        if not self._connected:
            return None
        try:
            t = timeout if timeout > 0 else self.read_timeout
            data = await asyncio.wait_for(self._queue.get(), timeout=t)
            self._packets_received += 1
            return data
        except asyncio.TimeoutError:
            return None
        except Exception:
            logger.exception("UDP receive error")
            return None

    async def close(self) -> None:
        """Close the UDP endpoint."""
        self._connected = False
        if self._transport:
            self._transport.close()
        logger.info("UDP endpoint closed: %s", self._endpoint)

    @property
    def packets_sent(self) -> int:
        return self._packets_sent

    @property
    def packets_received(self) -> int:
        return self._packets_received

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str, int]:
        """Parse host:port from endpoint string."""
        url = endpoint.replace("udp://", "")
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            return host, int(port_str)
        return url, 9000


class _UDPQueueProtocol(asyncio.DatagramProtocol):
    """Internal datagram protocol that queues received data."""

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self._queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)
