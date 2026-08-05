"""Service Discovery module for ICYQuant.

Provides service registration, discovery, resolution, lease
management, and lifecycle tracking for distributed ICYQuant
services.

Architecture::

    ServiceDiscoveryManager
          ↓
    ServiceRegistry → RegistryAdapter (backend)
          ↓
    ServiceResolver → ServiceSelector (strategy)
          ↓
    ServiceInstance / ServiceEndpoint

Usage::

    from infrastructure.service_discovery import (
        ServiceDiscoveryManager, ServiceRegistry, ServiceInstance,
        ServiceStatus,
    )

    manager = ServiceDiscoveryManager()
    await manager.startup()
    await manager.get_registry().register(instance)
"""

# Exceptions
from .exceptions import (
    ServiceDiscoveryError,
    ServiceRegistrationError,
    ServiceDeregistrationError,
    ServiceNotFoundError,
    ServiceUnavailableError,
    NamespaceError,
    LeaseExpiredError,
    LeaseRenewalError,
    RegistryError,
    AdapterError,
    AdapterNotReadyError,
    AdapterConnectionError,
    ValidationError,
    ResolverError,
    DiscoveryTimeoutError,
)

# Models
from .models import (
    ServiceStatus,
    ServiceProtocol,
    ServiceEndpoint as ServiceEndpointModel,
    ServiceMetadata as ServiceMetadataModel,
    ServiceInstance as ServiceInstanceModel,
    ServiceInfo,
)

# Rich classes
from .endpoint import ServiceEndpoint
from .metadata import ServiceMetadata
from .instance import ServiceInstance
from .service import Service
from .namespace import Namespace, NamespaceManager, DEFAULT_NAMESPACES
from .selector import (
    ServiceSelector,
    RoundRobinSelector,
    RandomSelector,
    WeightedSelector,
    SelectorFactory,
)
from .validator import ServiceValidator
from .repository import ServiceRepository
from .lifecycle import ServiceLifecycle
from .lease import ServiceLease, LeaseManager
from .registry import InMemoryRegistryAdapter, ServiceRegistry
from .resolver import ServiceResolver
from .manager import ServiceDiscoveryManager

# Adapters
from .adapters import (
    RegistryAdapter,
    MemoryAdapter,
    EtcdAdapter,
    ConsulAdapter,
    KubernetesAdapter,
    AdapterFactory,
)

# Events, metrics, health, diagnostics
from .events import ServiceEventType, ServiceEvent, ServiceEventBus
from .metrics import ServiceDiscoveryMetrics
from .health import ServiceDiscoveryHealth
from .diagnostics import ServiceDiscoveryDiagnostics

__all__ = [
    # Exceptions
    "ServiceDiscoveryError", "ServiceRegistrationError",
    "ServiceDeregistrationError", "ServiceNotFoundError",
    "ServiceUnavailableError", "NamespaceError",
    "LeaseExpiredError", "LeaseRenewalError",
    "RegistryError", "AdapterError",
    "AdapterNotReadyError", "AdapterConnectionError",
    "ValidationError", "ResolverError", "DiscoveryTimeoutError",
    # Models
    "ServiceStatus", "ServiceProtocol",
    "ServiceEndpointModel", "ServiceMetadataModel",
    "ServiceInstanceModel", "ServiceInfo",
    # Rich classes
    "ServiceEndpoint", "ServiceMetadata", "ServiceInstance",
    "Service", "Namespace", "NamespaceManager", "DEFAULT_NAMESPACES",
    # Selectors
    "ServiceSelector", "RoundRobinSelector", "RandomSelector",
    "WeightedSelector", "SelectorFactory",
    # Components
    "ServiceValidator", "ServiceRepository",
    "ServiceLifecycle", "ServiceLease", "LeaseManager",
    "ServiceRegistry", "InMemoryRegistryAdapter",
    "ServiceResolver", "ServiceDiscoveryManager",
    # Adapters
    "RegistryAdapter", "MemoryAdapter", "EtcdAdapter",
    "ConsulAdapter", "KubernetesAdapter", "AdapterFactory",
    # Events, metrics, health, diagnostics
    "ServiceEventType", "ServiceEvent", "ServiceEventBus",
    "ServiceDiscoveryMetrics", "ServiceDiscoveryHealth",
    "ServiceDiscoveryDiagnostics",
]
