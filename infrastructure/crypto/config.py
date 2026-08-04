"""
Crypto platform configuration.

Provides configuration management for
the encryption platform, including algorithm
selection, KMS provider settings, and
envelope encryption parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constants import (
    AlgorithmName,
    DEFAULT_ENCRYPTION_ALGORITHM,
    DEFAULT_ENVELOPE_ALGORITHM,
    DEFAULT_HASH_ALGORITHM,
    DEFAULT_HMAC_ALGORITHM,
    DEFAULT_PASSWORD_ALGORITHM,
    DEFAULT_SIGNING_ALGORITHM,
    KMSProviderType,
)


@dataclass
class CryptoConfig:
    """
    Crypto platform configuration.

    Central configuration for all crypto
    platform operations, specifying algorithms,
    providers, and operational parameters.

    Attributes:
        default_encryption_algorithm: Default symmetric algorithm.
        default_signing_algorithm: Default signing algorithm.
        default_hash_algorithm: Default hashing algorithm.
        default_hmac_algorithm: Default HMAC algorithm.
        default_password_algorithm: Default password hashing algorithm.
        envelope_enabled: Whether envelope encryption is enabled.
        envelope_algorithm: Algorithm for envelope DEK encryption.
        kms_provider_type: Primary KMS provider type.
        kms_provider_config: KMS provider-specific configuration.
        key_cache_ttl_seconds: Key cache TTL in seconds.
        key_cache_max_size: Maximum cached keys.
        enable_key_rotation: Whether automatic key rotation is enabled.
        enable_kms_failover: Whether KMS failover is enabled.
        enable_circuit_breaker: Whether KMS circuit breaker is enabled.
        metadata: Additional configuration metadata.
    """

    default_encryption_algorithm: AlgorithmName = DEFAULT_ENCRYPTION_ALGORITHM
    default_signing_algorithm: AlgorithmName = DEFAULT_SIGNING_ALGORITHM
    default_hash_algorithm: AlgorithmName = DEFAULT_HASH_ALGORITHM
    default_hmac_algorithm: AlgorithmName = DEFAULT_HMAC_ALGORITHM
    default_password_algorithm: AlgorithmName = DEFAULT_PASSWORD_ALGORITHM
    envelope_enabled: bool = True
    envelope_algorithm: AlgorithmName = DEFAULT_ENVELOPE_ALGORITHM
    kms_provider_type: KMSProviderType = KMSProviderType.LOCAL
    kms_provider_config: Dict[str, Any] = field(default_factory=dict)
    key_cache_ttl_seconds: int = 3600
    key_cache_max_size: int = 256
    enable_key_rotation: bool = True
    enable_kms_failover: bool = True
    enable_circuit_breaker: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def kms_provider(self) -> str:
        """Get the KMS provider type name."""
        return self.kms_provider_type.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration to dictionary."""
        return {
            "default_encryption_algorithm": self.default_encryption_algorithm.value,
            "default_signing_algorithm": self.default_signing_algorithm.value,
            "default_hash_algorithm": self.default_hash_algorithm.value,
            "default_hmac_algorithm": self.default_hmac_algorithm.value,
            "default_password_algorithm": self.default_password_algorithm.value,
            "envelope_enabled": self.envelope_enabled,
            "envelope_algorithm": self.envelope_algorithm.value,
            "kms_provider_type": self.kms_provider_type.value,
            "kms_provider_config": self.kms_provider_config,
            "key_cache_ttl_seconds": self.key_cache_ttl_seconds,
            "key_cache_max_size": self.key_cache_max_size,
            "enable_key_rotation": self.enable_key_rotation,
            "enable_kms_failover": self.enable_kms_failover,
            "enable_circuit_breaker": self.enable_circuit_breaker,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> CryptoConfig:
        """Create configuration from dictionary."""
        return cls(
            default_encryption_algorithm=AlgorithmName(
                data.get("default_encryption_algorithm", DEFAULT_ENCRYPTION_ALGORITHM.value)
            ),
            default_signing_algorithm=AlgorithmName(
                data.get("default_signing_algorithm", DEFAULT_SIGNING_ALGORITHM.value)
            ),
            default_hash_algorithm=AlgorithmName(
                data.get("default_hash_algorithm", DEFAULT_HASH_ALGORITHM.value)
            ),
            default_hmac_algorithm=AlgorithmName(
                data.get("default_hmac_algorithm", DEFAULT_HMAC_ALGORITHM.value)
            ),
            default_password_algorithm=AlgorithmName(
                data.get("default_password_algorithm", DEFAULT_PASSWORD_ALGORITHM.value)
            ),
            envelope_enabled=data.get("envelope_enabled", True),
            envelope_algorithm=AlgorithmName(
                data.get("envelope_algorithm", DEFAULT_ENVELOPE_ALGORITHM.value)
            ),
            kms_provider_type=KMSProviderType(
                data.get("kms_provider_type", KMSProviderType.LOCAL.value)
            ),
            kms_provider_config=data.get("kms_provider_config", {}),
            key_cache_ttl_seconds=data.get("key_cache_ttl_seconds", 3600),
            key_cache_max_size=data.get("key_cache_max_size", 256),
            enable_key_rotation=data.get("enable_key_rotation", True),
            enable_kms_failover=data.get("enable_kms_failover", True),
            enable_circuit_breaker=data.get("enable_circuit_breaker", True),
        )


@dataclass
class AlgorithmConfig:
    """
    Per-algorithm configuration.

    Attributes:
        enabled: Whether the algorithm is enabled.
        params: Algorithm-specific parameters.
    """

    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KMSConfig:
    """
    KMS provider configuration.

    Attributes:
        provider_type: KMS provider type.
        endpoint: KMS endpoint URL.
        region: Cloud region (for cloud KMS).
        credentials: Authentication credentials.
        key_vault_path: Path to key vault or keys.
        timeout_seconds: Operation timeout.
        max_retries: Maximum retry attempts.
    """

    provider_type: KMSProviderType = KMSProviderType.LOCAL
    endpoint: str = ""
    region: str = ""
    credentials: Dict[str, str] = field(default_factory=dict)
    key_vault_path: str = "icyquant/keys"
    timeout_seconds: int = 30
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_type": self.provider_type.value,
            "endpoint": self.endpoint,
            "region": self.region,
            "credentials": "***" if self.credentials else {},
            "key_vault_path": self.key_vault_path,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
        }
