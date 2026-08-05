"""Service Discovery Platform subpackage for ICYQuant.

Provides the production-grade platform layer integrating service
discovery with bootstrap, runtime, cluster, gateway, and observability.

Architecture::

    DiscoveryPlatform
          ↓
    DiscoveryBootstrap → DiscoveryRuntime
          ↓
    DiscoveryService → ServiceDiscoveryGateway
          ↓
    ClusterPlatform → SnapshotAPI → TopologyAPI
"""

from __future__ import annotations

from .version import PlatformVersion, PlatformVersionManager
from .monitoring import PlatformMetrics
from .runtime_context import DiscoveryContext
from .container import DiscoveryContainer
from .bootstrap import DiscoveryBootstrap, BootstrapPhase
from .platform import DiscoveryPlatform
from .runtime import DiscoveryRuntime
from .integration import PlatformIntegration
from .gateway import ServiceDiscoveryGateway
from .discovery_service import DiscoveryService
from .snapshot_api import SnapshotAPI
from .topology import ServiceTopology
from .cluster import ClusterPlatform, ClusterNode
from .synchronizer import ClusterSynchronizer
from .publisher import DiscoveryPublisher, DiscoveryEvent
from .subscriber import DiscoverySubscriberManager
from .api import DiscoveryAPI
from .scheduler import PlatformScheduler, ScheduledTask
from .telemetry import PlatformTelemetry
from .health import PlatformHealth
from .diagnostics import PlatformDiagnostics
from .protection import PlatformProtection, ProtectionMode
from .recovery import PlatformRecovery
from .shutdown import GracefulShutdownManager

__all__ = [
    "PlatformVersion", "PlatformVersionManager",
    "PlatformMetrics",
    "DiscoveryContext",
    "DiscoveryContainer",
    "DiscoveryBootstrap", "BootstrapPhase",
    "DiscoveryPlatform",
    "DiscoveryRuntime",
    "PlatformIntegration",
    "ServiceDiscoveryGateway",
    "DiscoveryService",
    "SnapshotAPI",
    "ServiceTopology",
    "ClusterPlatform", "ClusterNode",
    "ClusterSynchronizer",
    "DiscoveryPublisher", "DiscoveryEvent",
    "DiscoverySubscriberManager",
    "DiscoveryAPI",
    "PlatformScheduler", "ScheduledTask",
    "PlatformTelemetry",
    "PlatformHealth",
    "PlatformDiagnostics",
    "PlatformProtection", "ProtectionMode",
    "PlatformRecovery",
    "GracefulShutdownManager",
]
