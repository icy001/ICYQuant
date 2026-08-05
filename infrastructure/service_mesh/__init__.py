"""Service Mesh module for ICYQuant.

Provides production-grade service mesh capabilities including
control plane, data plane, sidecar proxies, and traffic
management for distributed ICYQuant services.

Architecture::

    ServiceMesh (main entry)
          ↓
    ┌─────────────┬──────────────┐
    ControlPlane  DataPlane    MeshRuntime
    (policy/config) (proxy/traffic) (reload/sync)
          ↓
    Sidecar (per-service proxy)
          ↓
    Business Services (transparent integration)

Usage::

    from infrastructure.service_mesh import ServiceMesh

    mesh = ServiceMesh()
    await mesh.startup()
    sidecar = await mesh.create_sidecar("oms-sidecar", "oms")
    result = await mesh.handle_request("GET", "/orders")
    await mesh.shutdown()
"""

# Core models and exceptions
from .models import (
    MeshServiceStatus,
    SidecarState,
    ProxyType,
    ProxyProtocol,
    MeshEventType,
    MeshService,
    SidecarInstance,
    RoutingRule,
    ProxyConfig,
    MeshMetadata,
)
from .exceptions import (
    ServiceMeshError,
    MeshBootstrapError,
    MeshRuntimeError,
    SidecarError,
    SidecarStartError,
    SidecarConfigError,
    ProxyError,
    ProxyTimeoutError,
    CircuitBreakerOpenError,
    ControlPlaneError,
    DataPlaneError,
    ConfigurationError,
    MeshServiceError,
    MeshServiceNotFoundError,
    SynchronizationError,
    MeshShutdownError,
)

# Core infrastructure
from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .lifecycle import MeshLifecycle, MeshState
from .metrics import MeshMetrics
from .telemetry import MeshTelemetry
from .health import MeshHealth
from .diagnostics import MeshDiagnostics

# Core components
from .control_plane import ControlPlane
from .data_plane import DataPlane, CircuitBreaker
from .sidecar import Sidecar
from .proxy import MeshProxy
from .runtime import MeshRuntime
from .bootstrap import MeshBootstrap, BootstrapPhase
from .manager import MeshManager
from .discovery import MeshDiscovery
from .configuration import MeshConfiguration
from .synchronization import MeshSynchronizer
from .registry import MeshRegistry
from .mesh import ServiceMesh

# Adapters
from .adapters import (
    InternalProxyAdapter,
    EnvoyProxyAdapter,
    MockProxyAdapter,
)

__all__ = [
    # Models
    "MeshServiceStatus",
    "SidecarState",
    "ProxyType",
    "ProxyProtocol",
    "MeshEventType",
    "MeshService",
    "SidecarInstance",
    "RoutingRule",
    "ProxyConfig",
    "MeshMetadata",
    # Exceptions
    "ServiceMeshError",
    "MeshBootstrapError",
    "MeshRuntimeError",
    "SidecarError",
    "SidecarStartError",
    "SidecarConfigError",
    "ProxyError",
    "ProxyTimeoutError",
    "CircuitBreakerOpenError",
    "ControlPlaneError",
    "DataPlaneError",
    "ConfigurationError",
    "MeshServiceError",
    "MeshServiceNotFoundError",
    "SynchronizationError",
    "MeshShutdownError",
    # Infrastructure
    "MeshContext",
    "MeshEvent",
    "MeshEventPublisher",
    "MeshLifecycle",
    "MeshState",
    "MeshMetrics",
    "MeshTelemetry",
    "MeshHealth",
    "MeshDiagnostics",
    # Core components
    "ControlPlane",
    "CircuitBreaker",
    "DataPlane",
    "Sidecar",
    "MeshProxy",
    "MeshRuntime",
    "MeshBootstrap",
    "BootstrapPhase",
    "MeshManager",
    "MeshDiscovery",
    "MeshConfiguration",
    "MeshSynchronizer",
    "MeshRegistry",
    "ServiceMesh",
    # Adapters
    "InternalProxyAdapter",
    "EnvoyProxyAdapter",
    "MockProxyAdapter",
]
