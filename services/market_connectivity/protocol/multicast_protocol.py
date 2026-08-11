"""
Multicast Protocol — IP Multicast transport implementation for
efficient one-to-many market data distribution.

Multicast enables a single data source to simultaneously deliver
market data to multiple consumers without duplicating bandwidth.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from typing import Any, Optional

from .protocol_manager import Protocol

logger = logging.getLogger(__name__)


class MulticastProtocol(Protocol):
    """
    IP Multicast protocol implementation for market data distribution.

    Provides efficient one-to-many data delivery using IP multicast
    groups, ideal for exchange market data feeds distributed to
    multiple internal consumers.

    Usage::

        multicast = MulticastProtocol()
        await multicast.connect("multicast://239.0.0.1:5000")
        # Subscribe to a multicast group
        await multicast.join_group("239.0.0.1")
        data = await multicast.receive()
        await multicast.close()
    """

    def __init__(
        self,
        buffer_size: int = 65507,
        read_timeout: float = 1.0,
        interface_ip: str = "0.0.0.0",
        ttl: int = 1,
    ) -> None:
        super().__init__()
        self.buffer_size = buffer_size
        self.read_timeout = read_timeout
        self.interface_ip = interface_ip
        self.ttl = ttl
        self._endpoint: str = ""
        self._connected: bool = False
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[asyncio.DatagramProtocol] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._groups: set[str] = set()
        self._packets_received: int = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def protocol_name(self) -> str:
        return "multicast"

    async def connect(self, endpoint: str, **kwargs: Any) -> bool:
        """Create a multicast listener."""
        self._endpoint = endpoint
        host, port = self._parse_endpoint(endpoint)
        try:
            logger.info("Opening multicast listener: %s:%d", host, port)
            loop = asyncio.get_event_loop()

            # Create a multicast socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", port))

            # Set multicast options
            mreq = struct.pack("4s4s", socket.inet_aton(host), socket.inet_aton(self.interface_ip))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)

            self._transport, self._protocol = await loop.create_datagram_endpoint(
                lambda: _MulticastQueueProtocol(self._queue),
                sock=sock,
            )
            self._groups.add(host)
            self._connected = True
            logger.info("Multicast joined group: %s:%d", host, port)
            return True
        except Exception:
            logger.exception("Multicast connection failed: %s:%d", host, port)
            return False

    async def send(self, data: Any) -> bool:
        """Send data to the multicast group."""
        if not self._connected or not self._transport:
            logger.error("Cannot send: Multicast not connected")
            return False
        try:
            payload = data if isinstance(data, bytes) else str(data).encode()
            self._transport.sendto(payload)
            return True
        except Exception:
            logger.exception("Multicast send error")
            return False

    async def receive(self, timeout: float = 0) -> Optional[bytes]:
        """Receive data from the multicast group."""
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
            logger.exception("Multicast receive error")
            return None

    async def join_group(self, group: str) -> bool:
        """Join an additional multicast group."""
        if group in self._groups:
            return True
        self._groups.add(group)
        logger.info("Joined multicast group: %s", group)
        return True

    async def leave_group(self, group: str) -> bool:
        """Leave a multicast group."""
        self._groups.discard(group)
        logger.info("Left multicast group: %s", group)
        return True

    async def close(self) -> None:
        """Close the multicast listener."""
        self._connected = False
        if self._transport:
            self._transport.close()
        self._groups.clear()
        logger.info("Multicast listener closed: %s", self._endpoint)

    @property
    def groups(self) -> list[str]:
        return list(self._groups)

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str, int]:
        """Parse host:port from endpoint string."""
        url = endpoint.replace("multicast://", "")
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            return host, int(port_str)
        return url, 5000


class _MulticastQueueProtocol(asyncio.DatagramProtocol):
    """Internal datagram protocol that queues received multicast data."""

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self._queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        logger.error("Multicast error: %s", exc)
