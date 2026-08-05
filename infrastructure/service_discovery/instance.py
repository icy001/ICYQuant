"""Service instance representation.

Provides a rich ``ServiceInstance`` class with status management,
endpoint conversion, and serialization support for the ICYQuant
service discovery module.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .endpoint import ServiceEndpoint
from .models import ServiceStatus, _parse_datetime, _parse_status

logger = logging.getLogger(__name__)


class ServiceInstance:
    """A registered instance of a service.

    Args:
        service_name: Logical name of the service.
        instance_id: Unique identifier for this instance.
        host: Hostname or IP address.
        port: TCP/UDP port number.
        version: Service version string.
        namespace: Namespace the instance belongs to.
        metadata: Instance metadata mapping.
        status: Current lifecycle status.
        weight: Load balancing weight.
        healthy: Whether the instance is currently healthy.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __slots__ = (
        "service_name",
        "instance_id",
        "host",
        "port",
        "version",
        "namespace",
        "metadata",
        "status",
        "weight",
        "healthy",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        service_name: str,
        instance_id: str,
        host: str,
        port: int,
        version: str = "1.0.0",
        namespace: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        status: ServiceStatus = ServiceStatus.CREATED,
        weight: int = 1,
        healthy: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        self.service_name = service_name
        self.instance_id = instance_id
        self.host = host
        self.port = int(port)
        self.version = version or "1.0.0"
        self.namespace = namespace or "default"
        self.metadata = dict(metadata) if metadata else {}
        self.status = status if isinstance(status, ServiceStatus) else ServiceStatus.CREATED
        self.weight = int(weight) if weight else 1
        self.healthy = bool(healthy)
        self.created_at = created_at if created_at is not None else datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else self.created_at

    def to_endpoint(self) -> ServiceEndpoint:
        """Build a ``ServiceEndpoint`` from this instance.

        Returns:
            A ``ServiceEndpoint`` with the instance's host, port, and
            protocol derived from metadata when available.
        """
        protocol = "http"
        if isinstance(self.metadata, dict):
            protocol = str(self.metadata.get("protocol", "http"))
        path = ""
        if isinstance(self.metadata, dict):
            path = str(self.metadata.get("path", ""))
        return ServiceEndpoint(
            host=self.host,
            port=self.port,
            protocol=protocol,
            path=path,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the instance to a dictionary.

        Enums are serialized as their values and datetime fields as
        ISO 8601 strings.
        """
        return {
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "namespace": self.namespace,
            "metadata": dict(self.metadata),
            "status": self.status.value,
            "weight": self.weight,
            "healthy": self.healthy,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceInstance:
        """Deserialize a service instance from a dictionary.

        Args:
            data: Dictionary containing instance fields.

        Returns:
            A new ``ServiceInstance`` instance.
        """
        if data is None:
            data = {}
        now = datetime.utcnow()
        created_at = _parse_datetime(data.get("created_at")) or now
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            service_name=str(data.get("service_name", "")),
            instance_id=str(data.get("instance_id", "")),
            host=str(data.get("host", "")),
            port=int(data.get("port", 0)),
            version=str(data.get("version", "1.0.0")),
            namespace=str(data.get("namespace", "default")),
            metadata=dict(data.get("metadata", {}) or {}),
            status=_parse_status(data.get("status")),
            weight=int(data.get("weight", 1)),
            healthy=bool(data.get("healthy", True)),
            created_at=created_at,
            updated_at=updated_at,
        )

    def is_healthy(self) -> bool:
        """Return whether the instance is healthy and available.

        Returns:
            True if the instance is marked healthy and its status is
            either ``REGISTERED`` or ``HEALTHY``.
        """
        if not self.healthy:
            return False
        return self.status in (ServiceStatus.REGISTERED, ServiceStatus.HEALTHY)

    def update_status(self, status: ServiceStatus) -> None:
        """Update the instance's lifecycle status.

        Args:
            status: The new status to apply.
        """
        if not isinstance(status, ServiceStatus):
            logger.warning(
                "Ignoring invalid status update for instance '%s': %r",
                self.instance_id,
                status,
            )
            return
        self.status = status
        self.updated_at = datetime.utcnow()
        if status == ServiceStatus.HEALTHY:
            self.healthy = True
        elif status == ServiceStatus.UNHEALTHY:
            self.healthy = False

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ServiceInstance):
            return NotImplemented
        return (
            self.service_name == other.service_name
            and self.instance_id == other.instance_id
            and self.namespace == other.namespace
        )

    def __hash__(self) -> int:
        return hash((self.service_name, self.instance_id, self.namespace))

    def __str__(self) -> str:
        return (
            f"{self.service_name}/{self.instance_id} "
            f"({self.host}:{self.port}) [{self.status.value}]"
        )

    def __repr__(self) -> str:
        return (
            f"ServiceInstance(service_name={self.service_name!r}, "
            f"instance_id={self.instance_id!r}, host={self.host!r}, "
            f"port={self.port!r}, status={self.status.value!r})"
        )
