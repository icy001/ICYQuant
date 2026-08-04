"""
Decryption pipeline.

Orchestrates the decryption process
from encrypted payload through algorithm
selection, envelope decryption, and
KMS integration to recover plaintext.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..registry import AlgorithmRegistry
from ..exceptions import CryptoDecryptionError
from .encrypt import EncryptionResult


@dataclass
class DecryptionResult:
    """
    Decryption operation result.

    Attributes:
        plaintext: Decrypted data.
        algorithm: Algorithm used.
        key_id: KMS key ID used.
        metadata: Additional metadata.
    """

    plaintext: bytes = b""
    algorithm: str = ""
    key_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecryptionPipeline:
    """
    Decryption pipeline orchestrator.

    Manages the decryption workflow including:
    - Algorithm selection
    - Encrypted DEK recovery
    - KMS key unwrapping
    - Data decryption

    Usage:
        pipeline = DecryptionPipeline(
            registry=registry,
            kms_provider=kms,
        )
        result = await pipeline.decrypt(
            encrypted_result,
        )
    """

    def __init__(
        self,
        registry: AlgorithmRegistry,
        kms_provider: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._kms_provider = kms_provider

    async def decrypt(
        self,
        encrypted: EncryptionResult,
        key: Optional[bytes] = None,
        **kwargs: Any,
    ) -> DecryptionResult:
        """
        Decrypt data through the pipeline.

        Args:
            encrypted: EncryptionResult to decrypt.
            key: Direct key (for non-envelope mode).

        Returns:
            DecryptionResult with plaintext.
        """
        try:
            algo = self._registry.get(encrypted.algorithm)

            # Decode inputs
            ciphertext = base64.b64decode(encrypted.ciphertext)
            nonce = (
                base64.b64decode(encrypted.nonce)
                if encrypted.nonce
                else None
            )
            aad = (
                base64.b64decode(encrypted.aad)
                if encrypted.aad
                else None
            )

            if encrypted.encrypted_dek and self._kms_provider:
                # Envelope decryption
                encrypted_dek = base64.b64decode(encrypted.encrypted_dek)
                dek = await self._kms_provider.decrypt_key(
                    key_id=encrypted.key_id,
                    encrypted_key=encrypted_dek,
                )

                plaintext = await algo.decrypt(
                    ciphertext=ciphertext,
                    key=dek,
                    nonce=nonce,
                    aad=aad,
                )
            elif key:
                # Direct decryption
                plaintext = await algo.decrypt(
                    ciphertext=ciphertext,
                    key=key,
                    nonce=nonce,
                    aad=aad,
                )
            else:
                raise CryptoDecryptionError(
                    algorithm=encrypted.algorithm,
                    reason="No key or encrypted DEK available",
                )

            return DecryptionResult(
                plaintext=plaintext,
                algorithm=encrypted.algorithm,
                key_id=encrypted.key_id,
                metadata={"mode": "envelope" if encrypted.encrypted_dek else "direct"},
            )
        except CryptoDecryptionError:
            raise
        except Exception as e:
            raise CryptoDecryptionError(
                algorithm=encrypted.algorithm,
                reason=str(e),
            )
