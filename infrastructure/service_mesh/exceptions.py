"""Exceptions for ICYQuant Service Mesh."""

from __future__ import annotations


class ServiceMeshError(Exception):
    """Base exception for service mesh errors."""

    pass


class MeshBootstrapError(ServiceMeshError):
    """Failed to bootstrap the service mesh."""

    pass


class MeshRuntimeError(ServiceMeshError):
    """Runtime error in the service mesh."""

    pass


class SidecarError(ServiceMeshError):
    """Error with a sidecar proxy."""

    pass


class SidecarStartError(SidecarError):
    """Failed to start a sidecar proxy."""

    pass


class SidecarConfigError(SidecarError):
    """Invalid sidecar configuration."""

    pass


class ProxyError(ServiceMeshError):
    """Error in proxy handling."""

    pass


class ProxyTimeoutError(ProxyError):
    """Proxy request timed out."""

    pass


class CircuitBreakerOpenError(ProxyError):
    """Circuit breaker is open."""

    pass


class ControlPlaneError(ServiceMeshError):
    """Error in control plane operations."""

    pass


class DataPlaneError(ServiceMeshError):
    """Error in data plane operations."""

    pass


class ConfigurationError(ServiceMeshError):
    """Invalid mesh configuration."""

    pass


class MeshServiceError(ServiceMeshError):
    """Error with mesh service registration or lookup."""

    pass


class MeshServiceNotFoundError(MeshServiceError):
    """Requested service not found in the mesh."""

    pass


class SynchronizationError(ServiceMeshError):
    """Error during mesh synchronization."""

    pass


class MeshShutdownError(ServiceMeshError):
    """Error during mesh shutdown."""

    pass
