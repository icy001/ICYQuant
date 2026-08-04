"""
AWS Key Management Service provider.

Provides integration with AWS KMS for
cloud-based key management and encryption
operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..config import KMSConfig
from ..exceptions import CryptoKMSError
from .provider import KMSKeyInfo, KMSProvider

logger = logging.getLogger(__name__)


class AWSKMSProvider(KMSProvider):
    """
    AWS Key Management Service provider.

    Integrates with AWS KMS for managed key
    encryption and decryption operations in
    the AWS cloud environment.

    Configuration:
        region: AWS region
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key
        kms_key_id: Default KMS key ID
    """

    def __init__(self, config: KMSConfig) -> None:
        super().__init__(config)
        self._name = "aws_kms"
        self._client: Any = None
        self._region = config.region or "us-east-1"

    async def initialize(self) -> None:
        """Initialize AWS KMS client."""
        try:
            import boto3
            self._client = boto3.client(
                "kms",
                region_name=self._region,
                aws_access_key_id=self._config.credentials.get("access_key_id"),
                aws_secret_access_key=self._config.credentials.get("secret_access_key"),
            )
            self._initialized = True
            logger.info("AWSKMSProvider initialized (region=%s)", self._region)
        except ImportError:
            logger.warning("boto3 not available, AWSKMSProvider in stub mode")
            self._initialized = True

    async def encrypt_key(
        self,
        key_id: str,
        data_key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Encrypt data key via AWS KMS."""
        try:
            if self._client:
                response = self._client.encrypt(
                    KeyId=key_id,
                    Plaintext=data_key,
                )
                return response["CiphertextBlob"]
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
        """Decrypt data key via AWS KMS."""
        try:
            if self._client:
                response = self._client.decrypt(
                    KeyId=key_id,
                    CiphertextBlob=encrypted_key,
                )
                return response["Plaintext"]
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
        algorithm: str = "",
        **kwargs: Any,
    ) -> KMSKeyInfo:
        """Create a new AWS KMS key."""
        try:
            if self._client:
                response = self._client.create_key(
                    Description=kwargs.get("description", key_id),
                    KeyUsage="ENCRYPT_DECRYPT",
                )
                key_metadata = response["KeyMetadata"]
                return KMSKeyInfo(
                    key_id=key_metadata["KeyId"],
                    version=1,
                    algorithm=algorithm,
                    created_at=datetime.utcnow(),
                    enabled=key_metadata.get("Enabled", True),
                    description=key_metadata.get("Description", ""),
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
        """Enable automatic rotation for an AWS KMS key."""
        try:
            if self._client:
                self._client.enable_key_rotation(KeyId=key_id)
                response = self._client.describe_key(KeyId=key_id)
                key_meta = response["KeyMetadata"]
                return KMSKeyInfo(
                    key_id=key_id,
                    version=key_meta.get("KeyVersionId", 0),
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
        """Schedule AWS KMS key deletion."""
        try:
            if self._client:
                self._client.schedule_key_deletion(
                    KeyId=key_id,
                    PendingWindowInDays=pending_days,
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
        """Get AWS KMS key info."""
        try:
            if self._client:
                response = self._client.describe_key(KeyId=key_id)
                meta = response["KeyMetadata"]
                return KMSKeyInfo(
                    key_id=key_id,
                    version=meta.get("KeyVersionId", 0),
                    algorithm=meta.get("EncryptionAlgorithms", [""])[0],
                    created_at=meta.get("CreationDate"),
                    enabled=meta.get("Enabled", True),
                    description=meta.get("Description", ""),
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
        """List AWS KMS keys."""
        try:
            if self._client:
                paginator = self._client.get_paginator("list_keys")
                result = []
                for page in paginator.paginate():
                    for key in page["Keys"]:
                        key_id = key["KeyId"]
                        if prefix and not key_id.startswith(prefix):
                            continue
                        result.append(KMSKeyInfo(
                            key_id=key_id,
                            version=key.get("KeyVersionId", 0),
                        ))
                return result
            return []
        except Exception as e:
            raise CryptoKMSError(
                provider=self._name,
                operation="list_keys",
                reason=str(e),
            )
