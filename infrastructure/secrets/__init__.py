"""
Secrets management platform.

Provides a comprehensive secrets management
system for the ICYQuant platform, including:

- Unified secrets manager with CRUD operations
- Provider framework (Vault, AWS, Azure, GCP, Local)
- Secret resolution with ${secret:...} references
- TTL-based caching with LRU eviction
- Access policy framework with role-based permissions
- Audit logging for compliance and forensics
- Prometheus-compatible metrics
- Health monitoring

Architecture:
    Application
          |
    SecretsManager
          |
          +---> SecretsRegistry (versioned storage)
          +---> SecretsCache (TTL cache)
          +---> SecretResolver (${secret:...} resolution)
          +---> SecretsProvider (pluggable backend)
          +---> SecretAccessPolicy (access control)
          +---> PermissionModel (roles)
          +---> SecretsAudit (audit logging)
          +---> SecretsMetrics (Prometheus metrics)
          +---> SecretsHealthCheck (health monitoring)

Usage:
    from infrastructure.secrets import SecretsManager

    manager = SecretsManager()
    await manager.startup()
    await manager.set("db/password", "secret123")
    value = await manager.get("db/password")
    resolved = manager.resolve_in_text("Connection string: ${secret:db/password}")
"""

# Config
from .config import SecretsConfig

# Constants
from .constants import (
    AccessLevel,
    AuditAction,
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_SECRET_SIZE,
    DEFAULT_NAMESPACE,
    DEFAULT_PROVIDER,
    DEFAULT_RATE_LIMIT,
    DEFAULT_ROTATION_DAYS,
    SecretCategory,
    SecretFormat,
    SecretStatus,
    SecretsProvider,
    ValidationSeverity,
)

# Exceptions
from .exceptions import (
    SecretAccessDeniedError,
    SecretCacheError,
    SecretEncryptionError,
    SecretExpiredError,
    SecretNotFoundError,
    SecretPolicyError,
    SecretProviderError,
    SecretResolutionError,
    SecretRotationError,
    SecretsError,
    SecretValidationError,
)

# Models
from .models import (
    SecretAccessEntry,
    SecretChangeEntry,
    SecretItem,
    SecretMetadata,
    ValidationIssue,
    ValidationResult,
)

# Registry
from .registry import SecretsRegistry

# Cache
from .cache import SecretsCache

# Provider
from .provider import (
    EnvironmentSecretsProvider,
    LocalSecretsProvider,
    ProviderFactory,
    SecretsProvider as SecretsProviderBase,
)

# Resolver
from .resolver import SecretResolver

# Manager
from .manager import SecretsManager

# Policy
from .policy import AccessRule, SecretAccessPolicy

# Permissions
from .permissions import (
    RolePermissions,
    PermissionModel,
    SecretAction,
    SecretRole,
)

# Validator
from .validator import SecretValidator

# Audit
from .audit import AuditEntry, SecretsAudit

# Metrics
from .metrics import SecretsMetrics

# Health
from .health import SecretsHealthCheck

# Lifecycle
from .lifecycle import (
    SecretLifecycle,
    LifecycleState,
    LifecycleManager,
    SecretsLifecycleState,
    SecretsLifecycle,
)

# Container
from .container import (
    SecretsContainer,
    create_default_container,
)

# Bootstrap
from .bootstrap import SecretsBootstrap

# Scheduler
from .scheduler import SecretsScheduler

# Telemetry
from .telemetry import SecretsTelemetry

# Monitoring
from .monitoring import SecretsMonitoring

# Diagnostics
from .diagnostics import SecretsDiagnostics

# Integrity
from .integrity import SecretsIntegrity

# Protection
from .protection import SecretsProtection

# Recovery
from .recovery import SecretsRecovery

# Service and Integration
from .service import SecurityService
from .integration import CryptoSecretsIntegration

# Credentials
from .credentials import (
    ApprovalMode,
    CredentialMetadata,
    CredentialType,
    RotationConfig,
    RotationStrategy,
)

# Expiration
from .expiration import (
    ExpirationLevel,
    ExpirationMonitor,
    ExpirationStatus,
)

# Certificate
from .certificate import (
    CertificateInfo,
    CertificateManager,
    CertificateStatus,
    CertificateType,
)

# Rotation
from .rotation import (
    ApprovalRequest,
    ApprovalResult,
    DualKeyTransition,
    ExecutionResult,
    RotationApproval,
    RotationAudit,
    RotationAuditEntry,
    RotationExecutor,
    RotationMetrics,
    RotationNotifier,
    RotationPolicy,
    RotationPolicyRegistry,
    RotationRollback,
    RotationScheduler,
    RotationValidator,
    RotationWorkflow,
    SecretRotationManager,
    TransitionPhase,
    WorkflowStatus,
    WorkflowStep,
)

# Utils
from .utils import (
    compute_checksum,
    decode_value,
    encode_value,
    format_timestamp,
    generate_secret_id,
    is_secret_reference,
    mask_secret_value,
    parse_secret_reference,
    parse_timestamp,
    resolve_references,
    sanitize_secret_key,
)

__all__ = [
    # Config
    "SecretsConfig",
    # Constants
    "SecretsProvider",
    "SecretCategory",
    "SecretFormat",
    "SecretStatus",
    "AuditAction",
    "AccessLevel",
    "ValidationSeverity",
    "DEFAULT_PROVIDER",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CACHE_MAX_SIZE",
    "DEFAULT_NAMESPACE",
    "DEFAULT_ROTATION_DAYS",
    "DEFAULT_MAX_SECRET_SIZE",
    "DEFAULT_RATE_LIMIT",
    # Exceptions
    "SecretsError",
    "SecretNotFoundError",
    "SecretAccessDeniedError",
    "SecretValidationError",
    "SecretEncryptionError",
    "SecretExpiredError",
    "SecretProviderError",
    "SecretCacheError",
    "SecretPolicyError",
    "SecretRotationError",
    "SecretResolutionError",
    # Models
    "SecretItem",
    "SecretMetadata",
    "SecretChangeEntry",
    "SecretAccessEntry",
    "ValidationIssue",
    "ValidationResult",
    # Registry
    "SecretsRegistry",
    # Cache
    "SecretsCache",
    # Provider
    "SecretsProviderBase",
    "LocalSecretsProvider",
    "EnvironmentSecretsProvider",
    "ProviderFactory",
    # Resolver
    "SecretResolver",
    # Manager
    "SecretsManager",
    # Policy
    "AccessRule",
    "SecretAccessPolicy",
    # Permissions
    "SecretAction",
    "SecretRole",
    "RolePermissions",
    "PermissionModel",
    # Validator
    "SecretValidator",
    # Audit
    "AuditEntry",
    "SecretsAudit",
    # Metrics
    "SecretsMetrics",
    # Health
    "SecretsHealthCheck",
    # Utils
    "mask_secret_value",
    "sanitize_secret_key",
    "parse_secret_reference",
    "is_secret_reference",
    "resolve_references",
    "compute_checksum",
    "encode_value",
    "decode_value",
    "generate_secret_id",
    "format_timestamp",
    "parse_timestamp",
    # Lifecycle
    "SecretLifecycle",
    "LifecycleState",
    "LifecycleManager",
    "SecretsLifecycleState",
    "SecretsLifecycle",
    # Container
    "SecretsContainer",
    "create_default_container",
    # Bootstrap
    "SecretsBootstrap",
    # Scheduler
    "SecretsScheduler",
    # Telemetry
    "SecretsTelemetry",
    # Monitoring
    "SecretsMonitoring",
    # Diagnostics
    "SecretsDiagnostics",
    # Integrity
    "SecretsIntegrity",
    # Protection
    "SecretsProtection",
    # Recovery
    "SecretsRecovery",
    # Service and Integration
    "SecurityService",
    "CryptoSecretsIntegration",
    # Credentials
    "CredentialType",
    "CredentialMetadata",
    "RotationConfig",
    "RotationStrategy",
    "ApprovalMode",
    # Expiration
    "ExpirationLevel",
    "ExpirationMonitor",
    "ExpirationStatus",
    # Certificate
    "CertificateType",
    "CertificateStatus",
    "CertificateInfo",
    "CertificateManager",
    # Rotation
    "SecretRotationManager",
    "RotationScheduler",
    "RotationWorkflow",
    "WorkflowStep",
    "WorkflowStatus",
    "DualKeyTransition",
    "TransitionPhase",
    "RotationPolicy",
    "RotationPolicyRegistry",
    "RotationValidator",
    "ApprovalRequest",
    "ApprovalResult",
    "RotationApproval",
    "RotationRollback",
    "RotationExecutor",
    "ExecutionResult",
    "RotationNotifier",
    "RotationAudit",
    "RotationAuditEntry",
    "RotationMetrics",
]
