"""
Plugin Framework for ICYQuant.

Provides a comprehensive plugin system for extending
platform functionality with capabilities, permissions,
and lifecycle management.

Architecture::

    Application
          ↓
    PluginManager / PluginService
          ↓
    PluginRegistry → PluginLoader → DependencyResolver
          ↓
    PluginLifecycle → PluginInstance
          ↓
    Capability / Permission / Context

Usage::

    from infrastructure.plugins import (
        PluginManager, PluginService, PluginManifest,
        Plugin, PluginContext, Capability, Permission,
        PluginState,
    )

    manager = PluginManager()
    await manager.initialize()
    await manager.install(manifest)
"""

# Exceptions
from .exceptions import (
    PluginError,
    PluginNotFoundError,
    PluginAlreadyExistsError,
    PluginLoadError,
    PluginInitError,
    PluginStartError,
    PluginStopError,
    PluginUnloadError,
    PluginValidationError,
    PluginDependencyError,
    PluginCircularDependencyError,
    PluginMissingDependencyError,
    PluginPermissionError,
    PluginCapabilityError,
    PluginManifestError,
    PluginConfigError,
    PluginStateError,
    PluginInstallError,
    PluginReloadError,
    PluginSandboxError,
    PluginSecurityError,
    PluginSignatureError,
    PluginTrustError,
    PluginResourceLimitError,
    PluginIsolationError,
    PluginSandboxViolationError,
    PluginNetworkAccessError,
    PluginFilesystemAccessError,
    PluginSecretAccessError,
    PluginWatchError,
)

# Models
from .models import (
    Plugin,
    PluginInstance,
    PluginInfo,
    PluginState,
    PluginPriority,
)

# Manifest
from .manifest import PluginManifest

# Metadata
from .metadata import PluginMetadata, MetadataRegistry

# Capabilities
from .capabilities import (
    Capability,
    CapabilityRequirement,
    CapabilityDeclaration,
    CapabilityRegistry,
)

# Permissions
from .permissions import (
    Permission,
    PermissionSet,
    PermissionChecker,
    DANGEROUS_PERMISSIONS,
)

# Context
from .context import PluginContext, ContextBuilder

# Configuration
from .configuration import PluginConfig, ConfigurationManager

# Hooks
from .hooks import HookRegistry, HookPoint

# Events
from .events import PluginEvent, PluginEventType, PluginEventBus

# Registry
from .registry import PluginRegistry

# Loader
from .loader import PluginLoader

# Loader sub-components
from .loader import (
    DirectoryScanner,
    PluginImporter,
    DependencyResolver2,
    PluginInstaller,
    PluginUninstaller,
    PluginReloader,
    FileWatcher,
    PluginVerifier,
    LoaderCache,
    LoaderMetrics,
    LoaderDiagnostics,
    LoaderValidator,
)

# Dependency
from .dependency import DependencyResolver

# Lifecycle
from .lifecycle import PluginLifecycle

# Validator
from .validator import PluginValidator

# Metrics
from .metrics import PluginMetrics

# Health
from .health import PluginHealth, HealthCheckResult

# Diagnostics
from .diagnostics import PluginDiagnostics, DiagnosticInfo

# Manager
from .manager import PluginManager

# Service
from .service import PluginService

# Marketplace
from .marketplace import (
    PluginMarketplace,
    MarketplaceRepository,
    MarketplaceRegistry,
    MarketplacePublisher,
    MarketplacePackage,
    MarketplaceInstaller,
    MarketplaceUpdater,
    MarketplaceRollback,
    MarketplaceChannels,
    MarketplaceCompatibility,
    MarketplaceDependency,
    MarketplaceResolver,
    MarketplaceSearch,
    MarketplaceDownloader,
    MarketplaceSignature,
    MarketplaceValidator,
    MarketplaceCache,
    MarketplaceAudit,
    MarketplaceMetrics,
    MarketplaceHealth,
    MarketplaceDiagnostics,
)

# Bootstrap / Runtime
from .bootstrap import PluginBootstrap
from .platform import PluginPlatform
from .runtime import PluginRuntime
from .runtime_context import RuntimeContext
from .container import Container
from .integration import PlatformIntegration
from .scheduler import PluginScheduler
from .synchronization import PluginSynchronization
from .discovery import RuntimeDiscovery
from .snapshot import PluginSnapshot, SnapshotManager
from .version import PluginVersion, VersionManager
from .publisher import PluginPublisher
from .subscriber import PluginSubscriber
from .monitoring import PluginMonitoring
from .telemetry import PluginTelemetry
from .protection import PluginProtection
from .shutdown import GracefulShutdown
from .api import PluginAPI

# Sandbox
from .sandbox import (
    Sandbox,
    SandboxRuntime,
    IsolationManager,
    SandboxPermissionGuard,
    SandboxCapabilityGuard,
    ResourceQuota,
    ResourceQuotaManager,
    FilesystemPolicy,
    NetworkPolicy,
    SecretAccessControl,
    CryptoProvider,
    SignatureVerifier,
    TrustStore,
    SandboxPolicy,
    PolicyEngine,
    PolicyDecision,
    PolicyRule,
    SandboxValidator,
    SandboxMonitor,
    SandboxMetrics,
    AuditLog,
    SandboxDiagnostics,
    RecoveryManager,
    SecurityPolicy,
)

__all__ = [
    # Exceptions
    "PluginError", "PluginNotFoundError", "PluginAlreadyExistsError",
    "PluginLoadError", "PluginInitError", "PluginStartError",
    "PluginStopError", "PluginUnloadError", "PluginValidationError",
    "PluginDependencyError", "PluginCircularDependencyError",
    "PluginMissingDependencyError", "PluginPermissionError",
    "PluginCapabilityError", "PluginManifestError",
    "PluginConfigError", "PluginStateError", "PluginInstallError",
    "PluginReloadError",
    "PluginSandboxError", "PluginSecurityError",
    "PluginSignatureError", "PluginTrustError",
    "PluginResourceLimitError", "PluginIsolationError",
    "PluginSandboxViolationError", "PluginNetworkAccessError",
    "PluginFilesystemAccessError", "PluginSecretAccessError",
    "PluginWatchError",
    # Models
    "Plugin", "PluginInstance", "PluginInfo",
    "PluginState", "PluginPriority",
    # Manifest
    "PluginManifest",
    # Metadata
    "PluginMetadata", "MetadataRegistry",
    # Capabilities
    "Capability", "CapabilityRequirement",
    "CapabilityDeclaration", "CapabilityRegistry",
    # Permissions
    "Permission", "PermissionSet", "PermissionChecker",
    "DANGEROUS_PERMISSIONS",
    # Context
    "PluginContext", "ContextBuilder",
    # Configuration
    "PluginConfig", "ConfigurationManager",
    # Hooks
    "HookRegistry", "HookPoint",
    # Events
    "PluginEvent", "PluginEventType", "PluginEventBus",
    # Registry
    "PluginRegistry",
    # Loader
    "PluginLoader",
    "DirectoryScanner", "PluginImporter", "DependencyResolver2",
    "PluginInstaller", "PluginUninstaller", "PluginReloader",
    "FileWatcher", "PluginVerifier", "LoaderCache",
    "LoaderMetrics", "LoaderDiagnostics", "LoaderValidator",
    # Dependency
    "DependencyResolver",
    # Lifecycle
    "PluginLifecycle",
    # Validator
    "PluginValidator",
    # Metrics
    "PluginMetrics",
    # Health
    "PluginHealth", "HealthCheckResult",
    # Diagnostics
    "PluginDiagnostics", "DiagnosticInfo",
    # Manager
    "PluginManager",
    # Service
    "PluginService",
    # Marketplace
    "PluginMarketplace", "MarketplaceRepository",
    "MarketplaceRegistry", "MarketplacePublisher",
    "MarketplacePackage", "MarketplaceInstaller",
    "MarketplaceUpdater", "MarketplaceRollback",
    "MarketplaceChannels", "MarketplaceCompatibility",
    "MarketplaceDependency", "MarketplaceResolver",
    "MarketplaceSearch", "MarketplaceDownloader",
    "MarketplaceSignature", "MarketplaceValidator",
    "MarketplaceCache", "MarketplaceAudit",
    "MarketplaceMetrics", "MarketplaceHealth",
    "MarketplaceDiagnostics",
    # Bootstrap / Runtime
    "PluginBootstrap", "PluginPlatform",
    "PluginRuntime", "RuntimeContext",
    "Container", "PlatformIntegration",
    "PluginScheduler", "PluginSynchronization",
    "RuntimeDiscovery", "PluginSnapshot", "SnapshotManager",
    "PluginVersion", "VersionManager",
    "PluginPublisher", "PluginSubscriber",
    "PluginMonitoring", "PluginTelemetry",
    "PluginProtection", "GracefulShutdown",
    "PluginAPI",
    # Sandbox
    "Sandbox", "SandboxRuntime", "IsolationManager",
    "SandboxPermissionGuard", "SandboxCapabilityGuard",
    "ResourceQuota", "ResourceQuotaManager",
    "FilesystemPolicy", "NetworkPolicy",
    "SecretAccessControl", "CryptoProvider",
    "SignatureVerifier", "TrustStore",
    "SandboxPolicy", "PolicyEngine",
    "PolicyDecision", "PolicyRule",
    "SandboxValidator", "SandboxMonitor",
    "SandboxMetrics", "AuditLog",
    "SandboxDiagnostics", "RecoveryManager",
    "SecurityPolicy",
]