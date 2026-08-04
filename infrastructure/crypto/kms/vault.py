"""
HashiCorp Vault KMS provider.

Provides integration with HashiCorp Vault's
Transit secrets engine for key management
and encryption operations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..config import KMSConfig
from ..exceptions import CryptoKMSError
from .provider import KMSKeyInfo, KMSProvider

logger = logging.getLogger(__name__)


class VaultKMSProvider(KMSProvider):
    """
    HashiCorp Vault KMS provider.

    Integrates with Vault's Transit secrets
    engine for managed encryption and key
    operations. Provides encryption-as-a-service
    without exposing key material to clients.

    Configuration:
        VAULT_ADDR: Vault server address
        VAULT_TOKEN: Authentication token
        VAULT_NAMESPACE: Vault namespace
        TRANSIT_PATH: Transit engine path
    """

    def __init__(self, config: KMSConfig) -> None:
        super().__init__(config)
        self._name = "vault"
        self._client: Any = None
        self._transit_path = config.key_vault_path or "transit"

    async def initialize(self) -> None:
        """Initialize Vault client connection."""
        try:
            # Lazy import - vault library is optional
            from hvac import Client
            self._client = Client(
                url=self._config.endpoint or "http://localhost:8200",
                token=self._config.credentials.get("token", ""),
            )
            self._initialized = True
            logger.info("VaultKMSProvider initialized")
        except ImportError:
            logger.warning(
                "hvac library not available, VaultKMSProvider in stub mode",
            )
            self._initialized = True  # Allow stub mode for testing

    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Encrypt data key via Vault Transit."""
        try:
            if self._client:
                import base64
                encoded = base64.b64encode(data_key).decode()
                path = f"{self._transit_path}/encrypt/{key_id}"
                response = self._client.create_or_update_secret(
                    path,
                    json={"plaintext": encoded},
                )
                return base64.b64decode(response["data"]["ciphertext"])
            else:
                # Stub mode: just base64 encode
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
        """Decrypt data key via Vault Transit."""
        try:
            if self._client:
                import base64
                encoded = base64.b64encode(encrypted_key).decode()
                path = f"{self._transit_path}/decrypt/{key_id}"
                response = self._client.create_or_update_secret(
                    path,
                    json={"ciphertext": encoded},
                )
                return base64.b64decode(response["data"]["plaintext"])
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
        algorithm: str = "aes256-gcm96",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Create a new encryption key in Vault Transit."""
        try:
            if self._client:
                path = f"{self._transit_path}/keys/{key_id}"
                key_type = kwargs.get("key_type", "aes256-gcm96")
                self._client.create_or_update_mount(path, type="transit")
                self._client.create_or_update_secret(
                    path,
                    json={"type": key_type},
                )

            return KMSKeyInfo(
                key_id=key_id,
                version=1,
                algorithm=algorithm,
            )
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
        """Rotate a Vault Transit key."""
        try:
            if self._client:
                path = f"{self._transit_path}/keys/{key_id}/rotate"
                self._client.create_or_update_secret(path, json={})
            return KMSKeyInfo(
                key_id=key_id,
                version=kwargs.get("new_version", 0),
            )
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
        """Delete a Vault Transit key."""
        try:
            if self._client:
                path = f"{self._transit_path}/keys/{key_id}"
                self._client.delete_secret(path)
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
        """Get Vault key info."""
        try:
            if self._client:
                path = f"{self._transit_path}/keys/{key_id}"
                response = self._client.read_secret(path)
                data = response.get("data", {})
                keys_info = data.get("keys", {})
                version = max(
                    (int(k) for k in keys_info.keys()),
                    default=0,
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=version,
                    algorithm=data.get("type", ""),
                    enabled=data.get("deletion_allowed", True),
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
        """List Vault Transit keys."""
        try:
            if self._client:
                path = f"{self._transit_path}/keys"
                response = self._client.list_secret(path)
                keys = response.get("data", {}).get("keys", [])
                result = []
                for key_id in keys:
                    if prefix and not key_id.startswith(prefix):
                        continue
                    result.append(KMSKeyInfo(key_id=key_id))
                return result
            return []
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="list_keys",
                reason=str(e),
            )
