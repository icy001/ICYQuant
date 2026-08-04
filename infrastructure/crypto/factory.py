"""
Crypto factory for creating algorithm and KMS instances.

Provides factory methods for instantiating
crypto algorithms and KMS providers
from configuration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .config import CryptoConfig, KMSConfig
from .constants import AlgorithmName, KMSProviderType
from .exceptions import CryptoAlgorithmNotSupportedError, CryptoKMSError
from .registry import AlgorithmRegistry, CryptoAlgorithm

logger = logging.getLogger(__name__)


class CryptoFactory:
    """
    Factory for creating crypto components.

    Creates algorithm instances and KMS
    provider instances from configuration,
    supporting dynamic provider selection.
    """

    def __init__(
        self,
        config: Optional[CryptoConfig] = None,
        registry: Optional[AlgorithmRegistry] = None,
    ) -> None:
        """
        Initialize factory.

        Args:
            config: Crypto configuration.
            registry: Algorithm registry.
        """
        self._config = config or CryptoConfig()
        self._registry = registry or AlgorithmRegistry()
        self._kms_providers: Dict[str, Any] = {}

    def get_algorithm(
        self,
        name: Optional[str] = None,
    ) -> CryptoAlgorithm:
        """
        Get an algorithm instance by name.

        Falls back to default encryption algorithm
        if no name is specified.

        Args:
            name: Algorithm name.

        Returns:
            Algorithm instance.
        """
        algo_name = name or self._config.default_encryption_algorithm.value
        return self._registry.get(algo_name)

    def get_algorithm_for_operation(
        self,
        operation: str,
        preferred_name: Optional[str] = None,
    ) -> CryptoAlgorithm:
        """
        Get the best algorithm for a crypto operation.

        Args:
            operation: Operation type.
            preferred_name: Preferred algorithm name.

        Returns:
            Algorithm instance.
        """
        if preferred_name:
            return self._registry.get(preferred_name)

        defaults: Dict[str, AlgorithmName] = {
            "encrypt": self._config.default_encryption_algorithm,
            "decrypt": self._config.default_encryption_algorithm,
            "sign": self._config.default_signing_algorithm,
            "verify": self._config.default_signing_algorithm,
            "hash": self._config.default_hash_algorithm,
            "hmac": self._config.default_hmac_algorithm,
            "password": self._config.default_password_algorithm,
        }

        algo_name = defaults.get(
            operation, self._config.default_encryption_algorithm
        )
        return self._registry.get(algo_name.value)

    def create_kms_provider(
        self,
        config: Optional[KMSConfig] = None,
    ) -> Any:
        """
        Create a KMS provider instance.

        Args:
            config: KMS configuration.

        Returns:
            KMS provider instance.
        """
        kms_config = config or KMSConfig(
            provider_type=self._config.kms_provider_type,
            **self._config.kms_provider_config,
        )

        provider_type = kms_config.provider_type

        # Lazy import to avoid circular dependencies
        if provider_type == KMSProviderType.LOCAL:
            from .kms.local import LocalKMSProvider
            return LocalKMSProvider(config=kms_config)
        elif provider_type == KMSProviderType.VAULT:
            from .kms.vault import VaultKMSProvider
            return VaultKMSProvider(config=kms_config)
        elif provider_type == KMSProviderType.AWS_KMS:
            from .kms.aws import AWSKMSProvider
            return AWSKMSProvider(config=kms_config)
        elif provider_type == KMSProviderType.AZURE_KEY_VAULT:
            from .kms.azure import AzureKeyVaultProvider
            return AzureKeyVaultProvider(config=kms_config)
        elif provider_type == KMSProviderType.GCP_KMS:
            from .kms.gcp import GCPKMSProvider
            return GCPKMSProvider(config=kms_config)
        else:
            raise CryptoKMSError(
                provider=provider_type.value,
                operation="create",
                reason=f"Unsupported KMS provider: {provider_type.value}",
            )

    def register_kms_provider(
        self,
        name: str,
        provider: Any,
    ) -> None:
        """Register a custom KMS provider."""
        self._kms_providers[name] = provider

    def get_config(self) -> CryptoConfig:
        """Get current crypto configuration."""
        return self._config

    def update_config(self, config: CryptoConfig) -> None:
        """Update crypto configuration."""
        self._config = config

    def get_stats(self) -> Dict[str, Any]:
        """Get factory statistics."""
        return {
            "registered_algorithms": self._registry.count(),
            "registered_kms_providers": len(self._kms_providers),
            "config": self._config.to_dict(),
        }
