"""
Envelope encryption.

Implements envelope encryption pattern
where a Data Encryption Key (DEK) is
generated for each encryption operation
and wrapped by a Key Encryption Key
(KEK) stored in a KMS provider.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import CryptoConfig
from .exceptions import CryptoEnvelopeError
from .registry import AlgorithmRegistry

logger = logging.getLogger(__name__)


@dataclass
class EnvelopeEncryptedData:
    """
    Envelope encrypted data structure.

    Represents the complete envelope
    encryption output including encrypted
    data, encrypted DEK, and metadata.

    Attributes:
        ciphertext: Encrypted data (base64).
        encrypted_dek: Encrypted DEK (base64).
        nonce: Nonce used (base64).
        key_id: KMS key ID used.
        algorithm: Algorithm used.
        aad: Additional authenticated data.
        version: Format version.
        created_at: Encryption timestamp.
    """

    ciphertext: str = ""
    encrypted_dek: str = ""
    nonce: str = ""
    key_id: str = ""
    algorithm: str = ""
    aad: str = ""
    version: str = "1.0"
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": self.ciphertext,
            "encrypted_dek": self.encrypted_dek,
            "nonce": self.nonce,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "aad": self.aad,
            "version": self.version,
            "created_at": (
                self.created_at.isoformat() + "Z"
                if self.created_at
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EnvelopeEncryptedData:
        """Create from dictionary."""
        created_at = data.get("created_at")
        if created_at:
            try:
                from datetime import timezone
                created_at = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                )
            except Exception:
                created_at = None

        return cls(
            ciphertext=data.get("ciphertext", ""),
            encrypted_dek=data.get("encrypted_dek", ""),
            nonce=data.get("nonce", ""),
            key_id=data.get("key_id", ""),
            algorithm=data.get("algorithm", ""),
            aad=data.get("aad", ""),
            version=data.get("version", "1.0"),
            created_at=created_at,
        )


class EnvelopeEncryption:
    """
    Envelope encryption implementation.

    Implements the envelope encryption
    pattern:
    1. Generate a random DEK (Data Encryption Key)
    2. Encrypt data with the DEK
    3. Encrypt the DEK with the KEK (Key Encryption Key) stored in KMS
    4. Store the encrypted DEK alongside the encrypted data

    Features:
    - DEK is generated per-encryption
    - KEK never leaves the KMS
    - Supports KEK rotation without re-encrypting data
    - Thread-safe DEK caching
    """

    def __init__(
        self,
        registry: AlgorithmRegistry,
        kms_provider: Any,
        config: Optional[CryptoConfig] = None,
    ) -> None:
        """
        Initialize envelope encryption.

        Args:
            registry: Algorithm registry.
            kms_provider: KMS provider for key wrapping.
            config: Crypto configuration.
        """
        self._registry = registry
        self._kms_provider = kms_provider
        self._config = config or CryptoConfig()
        self._lock = threading.RLock()
        self._dek_cache: Dict[str, Dict[str, Any]] = {}

    async def encrypt(
        self,
        data: bytes,
        key_id: str,
        algorithm_name: Optional[str] = None,
        aad: Optional[bytes] = None,
        **kwargs: Any,
    ) -> EnvelopeEncryptedData:
        """
        Perform envelope encryption.

        Args:
            data: Plaintext data to encrypt.
            key_id: KMS KEK key ID.
            algorithm_name: Algorithm to use.
            aad: Additional authenticated data.

        Returns:
            EnvelopeEncryptedData with encrypted payload.
        """
        try:
            # Step 1: Get encryption algorithm
            algo_name = algorithm_name or self._config.envelope_algorithm.value
            algo = self._registry.get(algo_name)

            # Step 2: Generate DEK
            dek = os.urandom(32)
            nonce = os.urandom(12)

            # Step 3: Encrypt data with DEK
            encrypted_data = await algo.encrypt(
                data=data,
                key=dek,
                nonce=nonce,
                aad=aad,
            )

            # Step 4: Encrypt DEK with KMS
            encrypted_dek = await self._kms_provider.encrypt_key(
                key_id=key_id,
                data_key=dek,
            )

            # Step 5: Cache DEK temporarily for potential batch operations
            cache_key = f"{key_id}:{nonce.hex()}"
            with self._lock:
                self._dek_cache[cache_key] = {
                    "dek": dek,
                    "timestamp": datetime.utcnow(),
                }

            return EnvelopeEncryptedData(
                ciphertext=base64.b64encode(encrypted_data).decode(),
                encrypted_dek=base64.b64encode(encrypted_dek).decode(),
                nonce=base64.b64encode(nonce).decode(),
                key_id=key_id,
                algorithm=algo_name,
                aad=base64.b64encode(aad).decode() if aad else "",
                version="1.0",
                created_at=datetime.utcnow(),
            )
        except CryptoEnvelopeError:
            raise
        except Exception as e:
            raise CryptoEnvelopeError(
                stage="encrypt",
                reason=str(e),
            )

    async def decrypt(
        self,
        envelope: EnvelopeEncryptedData,
        **kwargs: Any,
    ) -> bytes:
        """
        Perform envelope decryption.

        Args:
            envelope: EnvelopeEncryptedData to decrypt.

        Returns:
            Decrypted plaintext.
        """
        try:
            # Step 1: Get algorithm
            algo = self._registry.get(envelope.algorithm)

            # Step 2: Decode components
            encrypted_data = base64.b64decode(envelope.ciphertext)
            encrypted_dek = base64.b64decode(envelope.encrypted_dek)
            nonce = base64.b64decode(envelope.nonce)
            aad = (
                base64.b64decode(envelope.aad)
                if envelope.aad
                else None
            )

            # Step 3: Decrypt DEK with KMS
            dek = await self._kms_provider.decrypt_key(
                key_id=envelope.key_id,
                encrypted_key=encrypted_dek,
            )

            # Step 4: Decrypt data with DEK
            plaintext = await algo.decrypt(
                ciphertext=encrypted_data,
                key=dek,
                nonce=nonce,
                aad=aad,
            )

            return plaintext
        except CryptoEnvelopeError:
            raise
        except Exception as e:
            raise CryptoEnvelopeError(
                stage="decrypt",
                reason=str(e),
            )

    async def re_encrypt_dek(
        self,
        envelope: EnvelopeEncryptedData,
        new_key_id: str,
        **kwargs: Any,
    ) -> EnvelopeEncryptedData:
        """
        Re-encrypt the DEK with a new KEK.

        Used during KEK rotation to re-wrap
        the DEK without re-encrypting the
        actual data.

        Args:
            envelope: Original envelope.
            new_key_id: New KMS key ID.

        Returns:
            Updated EnvelopeEncryptedData.
        """
        try:
            # Decrypt DEK with old KEK
            encrypted_dek = base64.b64decode(envelope.encrypted_dek)
            dek = await self._kms_provider.decrypt_key(
                key_id=envelope.key_id,
                encrypted_key=encrypted_dek,
            )

            # Re-encrypt DEK with new KEK
            new_encrypted_dek = await self._kms_provider.encrypt_key(
                key_id=new_key_id,
                data_key=dek,
            )

            # Return updated envelope
            return EnvelopeEncryptedData(
                ciphertext=envelope.ciphertext,  # Unchanged
                encrypted_dek=base64.b64encode(new_encrypted_dek).decode(),
                nonce=envelope.nonce,
                key_id=new_key_id,
                algorithm=envelope.algorithm,
                aad=envelope.aad,
                version=envelope.version,
                created_at=datetime.utcnow(),
            )
        except Exception as e:
            raise CryptoEnvelopeError(
                stage="re_encrypt_dek",
                reason=str(e),
            )

    def clear_dek_cache(self) -> None:
        """Clear the DEK cache."""
        with self._lock:
            self._dek_cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached DEKs."""
        with self._lock:
            return len(self._dek_cache)
