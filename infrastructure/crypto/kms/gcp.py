"""
Google Cloud KMS provider.

Provides integration with Google Cloud
KMS for cloud-based key management
and encryption operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..config import KMSConfig
from ..exceptions import CryptoKMSError
from .provider import KMSKeyInfo, KMSProvider

logger = logging.getLogger(__name__)


class GCPKMSProvider(KMSProvider):
    """
    Google Cloud KMS provider.

    Integrates with Google Cloud KMS
    for managed key encryption operations
    in the GCP cloud environment.

    Configuration:
        project_id: GCP project ID
        location: GCP location (e.g., global)
        key_ring_id: GCP KMS key ring ID
        service_account_json: Service account key path
    """

    def __init__(self, config: KMSConfig) -> None:
        super().__init__(config)
        self._name = "gcp_kms"
        self._client: Any = None
        self._project_id = config.credentials.get("project_id", "")
        self._location = config.region or "global"
        self._key_ring_id = config.key_vault_path or "icyquant"

    async def initialize(self) -> None:
        """Initialize GCP KMS client."""
        try:
            from google.cloud import kms_v1
            from google.oauth2 import service_account

            sa_path = self._config.credentials.get(
                "service_account_json", ""
            )
            if sa_path:
                credentials = service_account.Credentials.from_service_account_file(
                    sa_path,
                )
            else:
                from google.auth import default
                credentials, _ = default()

            self._client = kms_v1.KeyManagementServiceClient(
                credentials=credentials,
            )
            self._initialized = True
            logger.info("GCPKMSProvider initialized")
        except ImportError:
            logger.warning(
                "Google Cloud SDK not available, GCPKMSProvider in stub mode",
            )
            self._initialized = True

    def _resource_name(self, key_id: str) -> str:
        """Build GCP KMS resource name."""
        return (
            f"projects/{self._project_id}"
            f"/locations/{self._location}"
            f"/keyRings/{self._key_ring_id}"
            f"/cryptoKeys/{key_id}"
        )

    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Encrypt data key via GCP KMS."""
        try:
            if self._client:
                import base64
                response = self._client.encrypt(
                    name=self._resource_name(key_id),
                    plaintext=data_key,
                )
                return response.ciphertext
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
        """Decrypt data key via GCP KMS."""
        try:
            if self._client:
                response = self._client.decrypt(
                    name=self._resource_name(key_id),
                    ciphertext=encrypted_key,
                )
                return response.plaintext
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
        algorithm: str = "GOOGLE_SYMMETRIC_ENCRYPTION",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Create a new GCP KMS key."""
        try:
            if self._client:
                parent = (
                    f"projects/{self._project_id}"
                    f"/locations/{self._location}"
                    f"/keyRings/{self._key_ring_id}"
                )
                crypto_key = {
                    "purpose": "ENCRYPT_DECRYPT",
                    "rotation_period": {},
                }
                response = self._client.create_crypto_key(
                    parent=parent,
                    crypto_key_id=key_id,
                    crypto_key=crypto_key,
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=1,
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
        """Rotate a GCP KMS key."""
        try:
            if self._client:
                response = self._client.create_crypto_key_version(
                    name=self._resource_name(key_id),
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=1,
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
        """Destroy a GCP KMS key version."""
        try:
            if self._client:
                self._client.destroy_crypto_key_version(
                    name=self._resource_name(key_id) + "/cryptoKeyVersions/1",
                )
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
        """Get GCP KMS key info."""
        try:
            if self._client:
                response = self._client.get_crypto_key(
                    name=self._resource_name(key_id),
                )
                return KMSKeyInfo(
                    key_id=key_id,
                    version=1,
                    created_at=datetime.utcnow(),
                    enabled=response.state == "ENABLED",
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
        """List GCP KMS keys."""
        try:
            if self._client:
                parent = (
                    f"projects/{self._project_id}"
                    f"/locations/{self._location}"
                    f"/keyRings/{self._key_ring_id}"
                )
                keys = self._client.list_crypto_keys(parent=parent)
                result = []
                for key in keys:
                    key_id = key.name.split("/")[-1]
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
