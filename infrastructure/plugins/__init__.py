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
]