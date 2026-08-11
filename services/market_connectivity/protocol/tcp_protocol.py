"""
TCP Protocol — Raw TCP transport implementation for low-latency
exchange communication with binary framing and buffering.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .protocol_manager import Protocol

logger = logging.getLogger(__name__)


class TCPProtocol(Protocol):
    """
    TCP protocol implementation for exchange connectivity.

    Provides low-latency, binary-protocol communication over TCP
    with custom framing, buffering, and connection management.

    Usage::

        tcp = TCPProtocol()
        await tcp.connect("tcp://exchange.example.com:8000")
        await tcp.send(b"\\x01\\x02\\x03")
        data = await tcp.receive()
        await tcp.close()
    """

    def __init__(
        self,
        buffer_size: int = 65536,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self.buffer_size = buffer_size
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._endpoint: str = ""
        self._connected: bool = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def protocol_name(self) -> str:
        return "tcp"

    async def connect(self, endpoint: str, **kwargs: Any) -> bool:
        """Establish a TCP connection."""
        self._endpoint = endpoint
        host, port = self._parse_endpoint(endpoint)
        try:
            logger.info("Connecting TCP: %s:%d", host, port)
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.connect_timeout,
            )
            self._connected = True
            logger.info("TCP connected: %s:%d", host, port)
            return True
        except Exception:
            logger.exception("TCP connection failed: %s:%d", host, port)
            return False

    async def send(self, data: Any) -> bool:
        """Send data over the TCP connection."""
        if not self._connected or not self._writer:
            logger.error("Cannot send: TCP not connected")
            return False
        try:
            payload = data if isinstance(data, bytes) else str(data).encode()
            self._writer.write(payload)
            await self._writer.drain()
            return True
        except Exception:
            logger.exception("TCP send error")
            self._connected = False
            return False

    async def receive(self, n: int = 0) -> Optional[bytes]:
        """Receive data from the TCP connection."""
        if not self._connected or not self._reader:
            logger.error("Cannot receive: TCP not connected")
            return None
        try:
            size = n if n > 0 else self.buffer_size
            data = await asyncio.wait_for(
                self._reader.read(size),
                timeout=self.read_timeout,
            )
            if not data:
                logger.warning("TCP connection closed by peer")
                self._connected = False
                return None
            return data
        except asyncio.TimeoutError:
            logger.warning("TCP read timeout")
            return None
        except Exception:
            logger.exception("TCP receive error")
            return None

    async def receive_exactly(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes from the TCP connection."""
        if not self._connected or not self._reader:
            return None
        try:
            data = await asyncio.wait_for(
                self._reader.readexactly(n),
                timeout=self.read_timeout,
            )
            return data
        except Exception:
            logger.exception("TCP readexactly error")
            return None

    async def close(self) -> None:
        """Close the TCP connection."""
        self._connected = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        logger.info("TCP closed: %s", self._endpoint)

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str, int]:
        """Parse host:port from endpoint string."""
        url = endpoint.replace("tcp://", "").replace("ssl://", "")
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            return host, int(port_str)
        return url, 8000
