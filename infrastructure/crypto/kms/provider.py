"""
KMS provider base interface.

Defines the abstract interface for
all Key Management Service providers,
enabling consistent key operations
across different backends.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import KMSConfig
from ..exceptions import CryptoKMSError

logger = logging.getLogger(__name__)


@dataclass
class KMSKeyInfo:
    """
    Key metadata from KMS.

    Attributes:
        key_id: Unique key identifier.
        version: Key version number.
        algorithm: Algorithm name.
        created_at: Creation timestamp.
        enabled: Whether key is enabled.
        description: Key description.
        tags: Key tags.
    """

    key_id: str = ""
    version: int = 1
    algorithm: str = ""
    created_at: Optional[datetime] = None
    enabled: bool = True
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "version": self.version,
            "algorithm": self.algorithm,
            "created_at": (
                self.created_at.isoformat() + "Z"
                if self.created_at
                else None
            ),
            "enabled": self.enabled,
            "description": self.description,
            "tags": self.tags,
        }


@dataclass
class KMSProviderHealth:
    """
    KMS provider health status.

    Attributes:
        healthy: Whether the provider is healthy.
        latency_ms: Operation latency.
        error_message: Error message if unhealthy.
        last_check: Timestamp of last health check.
    """

    healthy: bool = True
    latency_ms: float = 0.0
    error_message: str = ""
    last_check: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "last_check": (
                self.last_check.isoformat() + "Z"
                if self.last_check
                else None
            ),
        }


class KMSProvider(ABC):
    """
    Abstract KMS provider base class.

    All KMS provider implementations must
    inherit from this class and implement
    the core key management operations.

    Operations:
    - encrypt_key: Encrypt a data key with the KEK
    - decrypt_key: Decrypt an encrypted data key
    - generate_key: Generate a new key in KMS
    - rotate_key: Rotate an existing key
    - delete_key: Schedule key for deletion
    - get_key_info: Get key metadata
    - list_keys: List all keys
    """

    def __init__(self, config: Optional[KMSConfig] = None) -> None:
        """
        Initialize KMS provider.

        Args:
            config: KMS configuration.
        """
        self._config = config or KMSConfig()
        self._name = "base"
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection to KMS provider."""
        ...

    @abstractmethod
    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Encrypt a data key using the KMS.

        Args:
            key_id: KMS key encryption key ID.
            data_key: Plaintext data key to encrypt.

        Returns:
            Encrypted data key ciphertext.
        """
        ...

    @abstractmethod
    async def decrypt_key(
        self,
        key_id: str,
        encrypted_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Decrypt an encrypted data key.

        Args:
            key_id: KMS key encryption key ID.
            encrypted_key: Encrypted data key.

        Returns:
            Decrypted plaintext data key.
        """
        ...

    @abstractmethod
    async def generate_key(
        self,
        key_id: str,
        algorithm: str = "",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """
        Generate a new key in the KMS.

        Args:
            key_id: Unique key identifier.
            algorithm: Algorithm for the key.

        Returns:
            KMSKeyInfo for the generated key.
        """
        ...

    @abstractmethod
    async def rotate_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """
        Rotate (create new version) of a KMS key.

        Args:
            key_id: Key to rotate.

        Returns:
            KMSKeyInfo for the new version.
        """
        ...

    @abstractmethod
    async def delete_key(
        self,
        key_id: str,
        pending_days: int = 30,
        **kwargs: Any,
    ) -> None:
        """
        Schedule a key for deletion.

        Args:
            key_id: Key to delete.
            pending_days: Days before permanent deletion.
        """
        ...

    @abstractmethod
    async def get_key_info(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """
        Get key metadata.

        Args:
            key_id: Key to query.

        Returns:
            KMSKeyInfo with key metadata.
        """
        ...

    @abstractmethod
    async def list_keys(
        self,
        prefix: str = "",
        **kwargs: Any,
    ) -> List[KMSKeyInfo]:
        """
        List keys in the KMS.

        Args:
            prefix: Key name prefix filter.

        Returns:
            List of KMSKeyInfo.
        """
        ...

    async def health_check(self) -> KMSProviderHealth:
        """
        Check KMS provider health.

        Returns:
            KMSProviderHealth status.
        """
        return KMSProviderHealth(
            healthy=self._initialized,
            last_check=datetime.utcnow(),
        )

    def get_name(self) -> str:
        """Get provider name."""
        return self._name

    def get_config(self) -> KMSConfig:
        """Get provider configuration."""
        return self._config
