"""
Vault subpackage for HashiCorp Vault integration.

Provides a complete Vault integration stack:
- Client: Async HTTP client with retries and pooling
- Authentication: Token, AppRole, Kubernetes, JWT/OIDC
- KV v2: Full versioned secret management
- Lease: Lifecycle tracking with auto-renewal
- Namespace: Multi-environment isolation
- HA Failover: Standby node failover
- Health: Comprehensive health monitoring

Architecture:
    VaultSecretsProvider (SecretsProvider interface)
          |
    VaultClient (HTTP transport)
          |
    +---> KVSecretsEngine (CRUD operations)
    +---> LeaseManager + LeaseRenewer (lease lifecycle)
    +---> VaultNamespaceManager (isolation)
    +---> VaultHealthChecker (monitoring)
    +---> FailoverManager (HA)

Usage:
    from infrastructure.secrets.vault import VaultSecretsProvider

    config = VaultConfig(address="http://vault:8200")
    provider = VaultSecretsProvider(config)
    await provider.startup()
    item = await provider.read("database/password")
    await provider.shutdown()
"""

from __future__ import annotations

# Config
from .config import (
    VaultAppRoleConfig,
    VaultAuthenticationConfig,
    VaultFailoverConfig,
    VaultJWTConfig,
    VaultKubernetesConfig,
    VaultLeaseConfig,
    VaultTLSConfig,
    VaultTokenConfig,
    VaultConfig,
)

# Client
from .client import VaultClient

# Exceptions
from .exceptions import (
    VaultAuthenticationError,
    VaultCircuitOpenError,
    VaultConnectionError,
    VaultError,
    VaultFailoverError,
    VaultHealthError,
    VaultLeaseError,
    VaultNamespaceError,
    VaultPermissionDeniedError,
    VaultRenewalError,
    VaultRevocationError,
    VaultSecretNotFoundError,
    VaultWriteError,
)

# Authentication
from .authenticator import VaultAuthenticator
from .token import TokenAuthenticator
from .approle import AppRoleAuthenticator
from .kubernetes import KubernetesAuthenticator
from .jwt import JWTAuthenticator

# KV Secrets Engine
from .kv import KVSecretsEngine

# Lease Management
from .lease import Lease, LeaseManager, LeaseState
from .renew import LeaseRenewer

# Namespace
from .namespace import VaultNamespaceManager

# Health
from .health import VaultHealthChecker

# Provider
from .provider import VaultSecretsProvider

__all__ = [
    # Config
    "VaultConfig",
    "VaultTLSConfig",
    "VaultAuthenticationConfig",
    "VaultAppRoleConfig",
    "VaultKubernetesConfig",
    "VaultJWTConfig",
    "VaultTokenConfig",
    "VaultFailoverConfig",
    "VaultLeaseConfig",
    # Client
    "VaultClient",
    # Exceptions
    "VaultError",
    "VaultConnectionError",
    "VaultAuthenticationError",
    "VaultPermissionDeniedError",
    "VaultSecretNotFoundError",
    "VaultWriteError",
    "VaultLeaseError",
    "VaultRenewalError",
    "VaultRevocationError",
    "VaultNamespaceError",
    "VaultHealthError",
    "VaultFailoverError",
    "VaultCircuitOpenError",
    # Authentication
    "VaultAuthenticator",
    "TokenAuthenticator",
    "AppRoleAuthenticator",
    "KubernetesAuthenticator",
    "JWTAuthenticator",
    # KV
    "KVSecretsEngine",
    # Lease
    "Lease",
    "LeaseState",
    "LeaseManager",
    "LeaseRenewer",
    # Namespace
    "VaultNamespaceManager",
    # Health
    "VaultHealthChecker",
    # Provider
    "VaultSecretsProvider",
]
