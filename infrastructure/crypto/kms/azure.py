"""
Azure Key Vault KMS provider.

Provides integration with Azure Key Vault
for cloud-based key management and
encryption operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..config import KMSConfig
from ..exceptions import CryptoKMSError
from .provider import KMSKeyInfo, KMSProvider

logger = logging.getLogger(__name__)


class AzureKeyVaultProvider(KMSProvider):
    """
    Azure Key Vault provider.

    Integrates with Azure Key Vault for
    managed key encryption and decryption
    operations in the Azure cloud.

    Configuration:
        vault_url: Azure Key Vault URL
        tenant_id: Azure tenant ID
        client_id: Azure client ID
        client_secret: Azure client secret
    """

    def __init__(self, config: KMSConfig) -> None:
        super().__init__(config)
        self._name = "azure_key_vault"
        self._client: Any = None
        self._vault_url = config.endpoint or config.key_vault_path

    async def initialize(self) -> None:
        """Initialize Azure Key Vault client."""
        try:
            from azure.keyvault.keys import KeyVaultClient
            from azure.identity import ClientSecretCredential

            credential = ClientSecretCredential(
                tenant_id=self._config.credentials.get("tenant_id", ""),
                client_id=self._config.credentials.get("client_id", ""),
                client_secret=self._config.credentials.get("client_secret", ""),
            )
            self._client = KeyVaultClient(
                vault_url=self._vault_url,
                credential=credential,
            )
            self._initialized = True
            logger.info("AzureKeyVaultProvider initialized")
        except ImportError:
            logger.warning(
                "Azure SDK not available, AzureKeyVaultProvider in stub mode",
            )
            self._initialized = True

    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Encrypt data key via Azure Key Vault."""
        try:
            if self._client:
                import base64
                from azure.keyvault.keys import KeyEncryptionAlgorithm

                result = self._client.encrypt(
                    key_name=key_id,
                    algorithm=KeyEncryptionAlgorithm.RSA_OAEP_256,
                    value=data_key,
                )
                return result
            else:
                import base64
                return base64.b64encode(data_key)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="encrypt_key",
                reason=str(e),
            )

    async def decrypt_key(
        self,
        key_id: str,
        encrypted_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Decrypt data key via Azure Key Vault."""
        try:
            if self._client:
                from azure.keyvault.keys import KeyEncryptionAlgorithm

                result = self._client.decrypt(
                    key_name=key_id,
                    algorithm=KeyEncryptionAlgorithm.RSA_OAEP_256,
                    value=encrypted_key,
                )
                return result
            else:
                import base64
                return base64.b64decode(encrypted_key)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="decrypt_key",
                reason=str(e),
            )

    async def generate_key(
        self,
        key_id: str,
        algorithm: str = "RSA",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Create a new key in Azure Key Vault."""
        try:
            if self._client:
                from azure.keyvault.keys import KeyType

                key_type = KeyType.RSA if algorithm == "RSA" else KeyType.EC
                key = self._client.create_rsa_key(
                    key_name=key_id,
                    key_size=kwargs.get("key_size", 2048),
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=key.version if hasattr(key, "version") else 1,
                    algorithm=algorithm,
                    created_at=datetime.utcnow(),
                )
            return KMSKeyInfo(key_id=key_id)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="generate_key",
                reason=str(e),
            )

    async def rotate_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Rotate an Azure Key Vault key."""
        try:
            if self._client:
                key = self._client.create_rsa_key(
                    key_name=key_id,
                    key_size=kwargs.get("key_size", 2048),
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=key.version if hasattr(key, "version") else 1,
                    created_at=datetime.utcnow(),
                )
            return KMSKeyInfo(key_id=key_id)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="rotate_key",
                reason=str(e),
            )

    async def delete_key(
        self,
        key_id: str,
        pending_days: int = 30,
        **kwargs: Any,
    ) -> None:
        """Delete an Azure Key Vault key."""
        try:
            if self._client:
                self._client.begin_delete_key(key_id)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="delete_key",
                reason=str(e),
            )

    async def get_key_info(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Get Azure Key Vault key info."""
        try:
            if self._client:
                key = self._client.get_key(key_id)
                return KMSKeyInfo(
                    key_id=key_id,
                    version=key.version if hasattr(key, "version") else 1,
                    enabled=not key.disabled if hasattr(key, "disabled") else True,
                    created_at=key.created_on if hasattr(key, "created_on") else None,
                )
            return KMSKeyInfo(key_id=key_id)
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="get_key_info",
                reason=str(e),
            )

    async def list_keys(
        self,
        prefix: str = "",
        **kwargs: Any,
    ) -> List[KMSKeyInfo]:
        """List Azure Key Vault keys."""
        try:
            if self._client:
                keys = self._client.list_keys()
                result = []
                for key in keys:
                    if prefix and not key.name.startswith(prefix):
                        continue
                    result.append(KMSKeyInfo(
                        key_id=key.name,
                        version=key.version if hasattr(key, "version") else 1,
                    ))
                return result
            return []
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="list_keys",
                reason=str(e),
            )
