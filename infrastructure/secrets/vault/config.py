"""
Vault-specific configuration.

Provides Pydantic models for configuring
Vault client connections, authentication,
and operational parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VaultTLSConfig(BaseModel):
    """TLS configuration for Vault connections."""

    enabled: bool = True
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    ca_cert: Optional[str] = None
    verify: bool = True


class VaultAppRoleConfig(BaseModel):
    """AppRole authentication configuration."""

    role_id: str = ""
    secret_id: str = ""
    mount_point: str = "approle"


class VaultKubernetesConfig(BaseModel):
    """Kubernetes authentication configuration."""

    role: str = ""
    service_account_token_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    mount_point: str = "kubernetes"
    kubernetes_ca_cert: Optional[str] = None


class VaultJWTConfig(BaseModel):
    """JWT/OIDC authentication configuration."""

    role: str = ""
    jwt_token: Optional[str] = None
    mount_point: str = "jwt"
    audience: str = ""
    issuer: str = ""


class VaultTokenConfig(BaseModel):
    """Token-based authentication configuration."""

    token: str = ""
    renew: bool = True


class VaultAuthenticationConfig(BaseModel):
    """Authentication configuration container."""

    method: str = "token"
    approle: Optional[VaultAppRoleConfig] = None
    kubernetes: Optional[VaultKubernetesConfig] = None
    jwt: Optional[VaultJWTConfig] = None
    token: Optional[VaultTokenConfig] = None


class VaultFailoverConfig(BaseModel):
    """High availability failover configuration."""

    enabled: bool = True
    standby_addresses: List[str] = Field(default_factory=list)
    health_check_interval: int = 10
    failure_threshold: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_timeout: int = 60


class VaultLeaseConfig(BaseModel):
    """Lease management configuration."""

    auto_renew: bool = True
    renew_buffer_seconds: int = 60
    max_lease_duration: int = 3600
    default_lease_ttl: int = 1800
    revoke_on_shutdown: bool = True


class VaultConfig(BaseModel):
    """
    Main Vault configuration.

    Controls all aspects of Vault client
    connections, authentication, and operations.
    """

    address: str = "http://localhost:8200"
    namespace: str = "icyquant"
    mount: str = "secret"
    mount_version: int = 2
    verify_tls: bool = True
    request_timeout: int = 10
    auto_renew: bool = True
    max_retries: int = 3
    retry_delay: float = 0.5
    connection_pool_size: int = 20
    tls: VaultTLSConfig = Field(default_factory=VaultTLSConfig)
    auth: VaultAuthenticationConfig = Field(default_factory=VaultAuthenticationConfig)
    failover: VaultFailoverConfig = Field(default_factory=VaultFailoverConfig)
    lease: VaultLeaseConfig = Field(default_factory=VaultLeaseConfig)
    extra_headers: Dict[str, str] = Field(default_factory=dict)

    @property
    def kv_path(self) -> str:
        """Get the full KV mount path."""
        return f"/{self.mount}"

    @property
    def api_base(self) -> str:
        """Get the API base URL."""
        return f"{self.address.rstrip('/')}/v1"
