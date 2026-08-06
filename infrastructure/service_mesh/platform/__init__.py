"""Service Mesh Platform for ICYQuant.

Provides production-grade service mesh platform capabilities including
runtime container, control plane API, plugin system, snapshot/restore,
rolling upgrade, and integration adapters.

Architecture::

    ServiceMeshPlatform (main entry)
          ↓
    ┌─────────────┬──────────────┬─────────────┐
    RuntimeContainer  ControlAPI    PluginManager
    (reload/sync)   (REST/API)    (lifecycle)
          ↓
    ┌─────────────┬──────────────┬─────────────┐
    Snapshot/Restore  UpgradeManager  Compatibility
    (disaster recovery) (zero-downtime) (version mgmt)
          ↓
    WorkflowAdapter / AIRuntimeAdapter / DiscoveryAdapter
"""

from __future__ import annotations

from .bootstrap import MeshPlatformBootstrap, PlatformBootstrapPhase
from .runtime import MeshPlatformRuntime
from .container import RuntimeContainer, RuntimeContainerManager, ContainerState
from .control_api import MeshControlAPI
from .control_service import MeshControlService
from .injector import SidecarInjector, InjectionMode, InjectionStatus
from .plugin_sdk import MeshPlugin, MeshPluginContext, PluginCategory
from .plugin_manager import MeshPluginManager, PluginState
from .snapshot import MeshSnapshot, SnapshotType
from .restore import MeshRestore
from .upgrade import RollingUpgradeManager, UpgradeState, UpgradeStrategy
from .compatibility import VersionCompatibilityManager, CompatibilityLevel
from .cluster import MeshClusterManager, ClusterNode, NodeState
from .workflow_adapter import WorkflowAdapter
from .ai_runtime_adapter import AIRuntimeAdapter
from .discovery_adapter import ServiceDiscoveryAdapter
from .configuration_adapter import ConfigurationPlatformAdapter
from .eventbus_adapter import PlatformEventBusAdapter, PlatformEvent
from .integration import ServiceMeshPlatform
from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics
from .diagnostics import PlatformDiagnostics
from .health import PlatformHealth

__all__ = [
    # Bootstrap
    "MeshPlatformBootstrap",
    "PlatformBootstrapPhase",
    # Runtime
    "MeshPlatformRuntime",
    "RuntimeContainer",
    "RuntimeContainerManager",
    "ContainerState",
    # Control
    "MeshControlAPI",
    "MeshControlService",
    # Injection
    "SidecarInjector",
    "InjectionMode",
    "InjectionStatus",
    # Plugin
    "MeshPlugin",
    "MeshPluginContext",
    "PluginCategory",
    "MeshPluginManager",
    "PluginState",
    # Snapshot/Restore
    "MeshSnapshot",
    "SnapshotType",
    "MeshRestore",
    # Upgrade
    "RollingUpgradeManager",
    "UpgradeState",
    "UpgradeStrategy",
    # Compatibility
    "VersionCompatibilityManager",
    "CompatibilityLevel",
    # Cluster
    "MeshClusterManager",
    "ClusterNode",
    "NodeState",
    # Adapters
    "WorkflowAdapter",
    "AIRuntimeAdapter",
    "ServiceDiscoveryAdapter",
    "ConfigurationPlatformAdapter",
    "PlatformEventBusAdapter",
    "PlatformEvent",
    # Platform
    "ServiceMeshPlatform",
    # Infrastructure
    "PlatformTelemetry",
    "PlatformMetrics",
    "PlatformDiagnostics",
    "PlatformHealth",
]
