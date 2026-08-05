"""Data models for ICYQuant Service Mesh.

Defines core data classes for mesh services, sidecar instances,
proxy configurations, routing rules, and mesh metadata.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MeshServiceStatus(str, Enum):
    """Status of a mesh service."""

    CREATED = "created"
    BOOTSTRAPPED = "bootstrapped"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class SidecarState(str, Enum):
    """State of a sidecar proxy."""

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    RELOADING = "reloading"
    DRAINING = "draining"
    STOPPED = "stopped"
    ERROR = "error"


class ProxyType(str, Enum):
    """Type of proxy adapter."""

    INTERNAL = "internal"
    ENVOY = "envoy"
    MOCK = "mock"


class ProxyProtocol(str, Enum):
    """Protocol supported by the proxy."""

    HTTP = "http"
    GRPC = "grpc"
    TCP = "tcp"


class MeshEventType(str, Enum):
    """Events emitted by the service mesh."""

    MESH_STARTED = "mesh_started"
    MESH_STOPPED = "mesh_stopped"
    MESH_RELOADED = "mesh_reloaded"
    POLICY_UPDATED = "policy_updated"
    PROXY_RELOADED = "proxy_reloaded"
    SIDECAR_CREATED = "sidecar_created"
    SIDECAR_STARTED = "sidecar_started"
    SIDECAR_STOPPED = "sidecar_stopped"
    SIDECAR_ERROR = "sidecar_error"
    ROUTE_ADDED = "route_added"
    ROUTE_REMOVED = "route_removed"
    CONFIGURATION_PUBLISHED = "configuration_published"
    SYNC_COMPLETED = "sync_completed"


class MeshService:
    """A service registered with the service mesh."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        version: str = "v1",
        status: MeshServiceStatus = MeshServiceStatus.CREATED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.version = version
        self.status = status
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @property
    def service_id(self) -> str:
        return f"{self.namespace}/{self.name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "namespace": self.namespace,
            "version": self.version,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SidecarInstance:
    """A sidecar proxy attached to a business service."""

    def __init__(
        self,
        sidecar_id: str,
        service_name: str,
        namespace: str = "default",
        proxy_type: ProxyType = ProxyType.INTERNAL,
        state: SidecarState = SidecarState.CREATED,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.sidecar_id = sidecar_id
        self.service_name = service_name
        self.namespace = namespace
        self.proxy_type = proxy_type
        self.state = state
        self.config = config or {}
        self.created_at = datetime.utcnow()
        self.last_heartbeat: Optional[datetime] = None
        self.error_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sidecar_id": self.sidecar_id,
            "service_name": self.service_name,
            "namespace": self.namespace,
            "proxy_type": self.proxy_type.value,
            "state": self.state.value,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": (
                self.last_heartbeat.isoformat()
                if self.last_heartbeat
                else None
            ),
            "error_count": self.error_count,
        }


class RoutingRule:
    """A routing rule for traffic management."""

    def __init__(
        self,
        rule_id: str,
        service: str,
        source: str = "*",
        destination: str = "",
        path: str = "/",
        methods: Optional[List[str]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        timeout_s: float = 30.0,
        weight: float = 1.0,
        enabled: bool = True,
    ) -> None:
        self.rule_id = rule_id
        self.service = service
        self.source = source
        self.destination = destination
        self.path = path
        self.methods = methods or ["GET", "POST", "PUT", "DELETE"]
        self.retry_policy = retry_policy or {
            "max_retries": 2,
            "backoff_ms": 100,
        }
        self.timeout_s = timeout_s
        self.weight = weight
        self.enabled = enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "service": self.service,
            "source": self.source,
            "destination": self.destination,
            "path": self.path,
            "methods": self.methods,
            "retry_policy": self.retry_policy,
            "timeout_s": self.timeout_s,
            "weight": self.weight,
            "enabled": self.enabled,
        }


class ProxyConfig:
    """Configuration for a proxy instance."""

    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 15001,
        protocol: ProxyProtocol = ProxyProtocol.HTTP,
        max_connections: int = 1024,
        timeout_s: float = 30.0,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True,
        enable_load_balance: bool = True,
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.protocol = protocol
        self.max_connections = max_connections
        self.timeout_s = timeout_s
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_retry = enable_retry
        self.enable_load_balance = enable_load_balance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listen_host": self.listen_host,
            "listen_port": self.listen_port,
            "protocol": self.protocol.value,
            "max_connections": self.max_connections,
            "timeout_s": self.timeout_s,
            "enable_circuit_breaker": self.enable_circuit_breaker,
            "enable_retry": self.enable_retry,
            "enable_load_balance": self.enable_load_balance,
        }


class MeshMetadata:
    """Metadata for the service mesh."""

    def __init__(
        self,
        mesh_id: str = "icyquant-mesh",
        version: str = "1.0.0",
        environment: str = "development",
        region: str = "local",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.mesh_id = mesh_id
        self.version = version
        self.environment = environment
        self.region = region
        self.labels = labels or {}
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mesh_id": self.mesh_id,
            "version": self.version,
            "environment": self.environment,
            "region": self.region,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
        }
