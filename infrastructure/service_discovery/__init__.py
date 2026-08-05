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

# Part 1.2 - Heartbeat, Health & Recovery
from .heartbeat import HeartbeatService
from .heartbeat_scheduler import HeartbeatScheduler
from .lease_manager import AsyncLeaseManager
from .probe import Probe, ProbeResult, TCPProbe, HTTPProbe, GRPCProbe, InternalProbe, ProbeFactory
from .health_checker import HealthChecker
from .health_monitor import HealthMonitor
from .readiness import ReadinessProbe
from .liveness import LivenessProbe
from .startup import StartupProbe
from .detector import PhiAccrualDetector
from .quarantine import QuarantineManager
from .expiration import LeaseExpiration
from .recovery import ServiceRecovery
from .scheduler import HealthScheduler
from .telemetry import ServiceDiscoveryTelemetry
from .policies import HealthPolicy, AlwaysHealthyPolicy, ThresholdPolicy, ConsecutiveFailurePolicy, AdaptivePolicy, PolicyFactory

# Part 1.3 - Intelligent Resolver & Load Balancer
from .resolver import (
    ResolveContext, ResolveStrategy, StrategyConfig,
    LoadBalancerSelector, RoundRobinLoadBalancer, WeightedLoadBalancer,
    LeastConnectionLoadBalancer, LeastLatencyLoadBalancer,
    RandomLoadBalancer, ConsistentHashLoadBalancer,
    LoadBalancer, ServiceRouter,
    LocalityRouter, VersionRouter, CanaryRouter, FeatureFlagRouter,
    HealthFilter, CircuitFilter,
    ResolverCache, ResolverMetrics, ResolverDiagnostics, ResolverTelemetry,
    IntelligentServiceResolver,
    RoundRobin, Weighted, LeastConnection, LeastLatency, Random, ConsistentHash,
)

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
    # Part 1.2 - Heartbeat, Health & Recovery
    "HeartbeatService", "HeartbeatScheduler",
    "AsyncLeaseManager",
    "Probe", "ProbeResult", "TCPProbe", "HTTPProbe", "GRPCProbe",
    "InternalProbe", "ProbeFactory",
    "HealthChecker", "HealthMonitor",
    "ReadinessProbe", "LivenessProbe", "StartupProbe",
    "PhiAccrualDetector", "QuarantineManager",
    "LeaseExpiration", "ServiceRecovery",
    "HealthScheduler", "ServiceDiscoveryTelemetry",
    "HealthPolicy", "AlwaysHealthyPolicy", "ThresholdPolicy",
    "ConsecutiveFailurePolicy", "AdaptivePolicy", "PolicyFactory",
    # Part 1.3 - Intelligent Resolver & Load Balancer
    "ResolveContext", "ResolveStrategy", "StrategyConfig",
    "LoadBalancerSelector", "RoundRobinLoadBalancer", "WeightedLoadBalancer",
    "LeastConnectionLoadBalancer", "LeastLatencyLoadBalancer",
    "RandomLoadBalancer", "ConsistentHashLoadBalancer",
    "LoadBalancer", "ServiceRouter",
    "LocalityRouter", "VersionRouter", "CanaryRouter", "FeatureFlagRouter",
    "HealthFilter", "CircuitFilter",
    "ResolverCache", "ResolverMetrics", "ResolverDiagnostics", "ResolverTelemetry",
    "IntelligentServiceResolver",
    # Individual LB components
    "RoundRobin", "Weighted", "LeastConnection", "LeastLatency", "Random", "ConsistentHash",
]
