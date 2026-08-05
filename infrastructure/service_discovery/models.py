"""Service discovery data models.

Defines the core data structures used by the ICYQuant service
discovery module, including service status, protocol enums, and the
ServiceInstance, ServiceEndpoint, ServiceMetadata, and ServiceInfo
dataclasses with serialization support.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass as _stdlib_dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

if sys.version_info >= (3, 10):
    dataclass = _stdlib_dataclass
else:  # pragma: no cover - Python 3.9 compatibility shim
    def dataclass(cls=None, **kwargs):
        """Compatibility wrapper for ``dataclass(slots=True)``.

        Python 3.9 does not support the ``slots`` argument (added in
        3.10). This wrapper accepts and drops ``slots`` on 3.9 so the
        same ``@dataclass(slots=True)`` source works across versions;
        on 3.10+ it delegates to the standard library unchanged.
        """
        kwargs.pop("slots", None)
        if cls is None:
            return lambda klass: _stdlib_dataclass(**kwargs)(klass)
        return _stdlib_dataclass(**kwargs)(cls)


class ServiceStatus(Enum):
    """Lifecycle status of a service instance."""

    CREATED = "created"
    REGISTERED = "registered"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEREGISTERED = "deregistered"
    REMOVED = "removed"


class ServiceProtocol(Enum):
    """Communication protocol supported by a service endpoint."""

    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    TCP = "tcp"
    UDP = "udp"
    WEBSOCKET = "websocket"


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a value into a datetime, returning None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _parse_status(value: Any) -> ServiceStatus:
    """Parse a value into a ServiceStatus enum."""
    if isinstance(value, ServiceStatus):
        return value
    if value is None:
        return ServiceStatus.CREATED
    try:
        return ServiceStatus(str(value))
    except (ValueError, TypeError):
        return ServiceStatus.CREATED


def _parse_protocol(value: Any) -> ServiceProtocol:
    """Parse a value into a ServiceProtocol enum."""
    if isinstance(value, ServiceProtocol):
        return value
    if value is None:
        return ServiceProtocol.HTTP
    try:
        return ServiceProtocol(str(value))
    except (ValueError, TypeError):
        return ServiceProtocol.HTTP


@dataclass(slots=True)
class ServiceEndpoint:
    """A network endpoint for a service instance.

    Attributes:
        host: Hostname or IP address.
        port: TCP/UDP port number.
        protocol: Protocol identifier (e.g. http, https, grpc).
        path: Optional URL path component.
        metadata: Optional endpoint metadata.
    """

    host: str
    port: int
    protocol: str = "http"
    path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the endpoint to a dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "path": self.path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceEndpoint:
        """Deserialize an endpoint from a dictionary."""
        if data is None:
            data = {}
        return cls(
            host=str(data.get("host", "")),
            port=int(data.get("port", 0)),
            protocol=str(data.get("protocol", "http")),
            path=str(data.get("path", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass(slots=True)
class ServiceMetadata:
    """Metadata describing a service's deployment attributes.

    Attributes:
        environment: Deployment environment (e.g. production, staging).
        region: Geographic region identifier.
        zone: Availability zone identifier.
        weight: Load balancing weight.
        protocol: Default protocol for the service.
        capabilities: List of capability identifiers.
        tags: List of free-form tags.
        labels: Key/value labels for filtering.
    """

    environment: str = ""
    region: str = ""
    zone: str = ""
    weight: int = 1
    protocol: str = "http"
    capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the metadata to a dictionary."""
        return {
            "environment": self.environment,
            "region": self.region,
            "zone": self.zone,
            "weight": self.weight,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "tags": list(self.tags),
            "labels": dict(self.labels),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceMetadata:
        """Deserialize metadata from a dictionary."""
        if data is None:
            data = {}
        return cls(
            environment=str(data.get("environment", "")),
            region=str(data.get("region", "")),
            zone=str(data.get("zone", "")),
            weight=int(data.get("weight", 1)),
            protocol=str(data.get("protocol", "http")),
            capabilities=list(data.get("capabilities", []) or []),
            tags=list(data.get("tags", []) or []),
            labels=dict(data.get("labels", {}) or {}),
        )


@dataclass(slots=True)
class ServiceInstance:
    """A registered instance of a service.

    Attributes:
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

    service_name: str
    instance_id: str
    host: str
    port: int
    version: str = "1.0.0"
    namespace: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.CREATED
    weight: int = 1
    healthy: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

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
        """Deserialize a service instance from a dictionary."""
        if data is None:
            data = {}
        now = datetime.utcnow()
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
            created_at=_parse_datetime(data.get("created_at")) or now,
            updated_at=_parse_datetime(data.get("updated_at")) or now,
        )


@dataclass(slots=True)
class ServiceInfo:
    """Lightweight summary information for a service.

    Attributes:
        name: Logical name of the service.
        namespace: Namespace the service belongs to.
        version: Latest known version of the service.
        instances: List of instance summary dictionaries.
        metadata: Service-level metadata.
    """

    name: str
    namespace: str = "default"
    version: str = ""
    instances: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the service info to a dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "version": self.version,
            "instances": [dict(i) for i in self.instances],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceInfo:
        """Deserialize service info from a dictionary."""
        if data is None:
            data = {}
        return cls(
            name=str(data.get("name", "")),
            namespace=str(data.get("namespace", "default")),
            version=str(data.get("version", "")),
            instances=[dict(i) for i in (data.get("instances", []) or [])],
            metadata=dict(data.get("metadata", {}) or {}),
        )
