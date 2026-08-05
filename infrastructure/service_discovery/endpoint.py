"""Service endpoint representation.

Provides a rich ``ServiceEndpoint`` class with URL construction,
serialization, and comparison support for the ICYQuant service
discovery module.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .models import ServiceProtocol

logger = logging.getLogger(__name__)


class ServiceEndpoint:
    """A network endpoint for reaching a service instance.

    Args:
        host: Hostname or IP address.
        port: TCP/UDP port number.
        protocol: Protocol identifier (e.g. http, https, grpc).
        path: Optional URL path component.
        metadata: Optional endpoint metadata mapping.
    """

    __slots__ = ("host", "port", "protocol", "path", "metadata")

    def __init__(
        self,
        host: str,
        port: int,
        protocol: str = "http",
        path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.protocol = protocol or "http"
        self.path = path or ""
        self.metadata = dict(metadata) if metadata else {}

    def to_url(self) -> str:
        """Build a URL string from the endpoint components.

        Returns:
            A URL of the form ``<protocol>://<host>:<port><path>``.
        """
        normalized_path = self.path
        if normalized_path and not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path
        return f"{self.protocol}://{self.host}:{self.port}{normalized_path}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the endpoint to a dictionary.

        Returns:
            Dictionary representation of the endpoint.
        """
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "path": self.path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceEndpoint:
        """Deserialize an endpoint from a dictionary.

        Args:
            data: Dictionary containing endpoint fields.

        Returns:
            A new ``ServiceEndpoint`` instance.
        """
        if data is None:
            data = {}
        return cls(
            host=str(data.get("host", "")),
            port=int(data.get("port", 0)),
            protocol=str(data.get("protocol", "http")),
            path=str(data.get("path", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    @staticmethod
    def _normalize_protocol(protocol: str) -> str:
        """Normalize a protocol string to its enum value when possible."""
        try:
            return ServiceProtocol(str(protocol)).value
        except (ValueError, TypeError):
            return str(protocol)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ServiceEndpoint):
            return NotImplemented
        return (
            self.host == other.host
            and self.port == other.port
            and self.protocol == other.protocol
            and self.path == other.path
        )

    def __hash__(self) -> int:
        return hash((self.host, self.port, self.protocol, self.path))

    def __str__(self) -> str:
        return self.to_url()

    def __repr__(self) -> str:
        return (
            f"ServiceEndpoint(host={self.host!r}, port={self.port!r}, "
            f"protocol={self.protocol!r}, path={self.path!r})"
        )
