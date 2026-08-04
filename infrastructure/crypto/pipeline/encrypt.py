"""
Encryption pipeline.

Orchestrates the encryption process
from plaintext input through algorithm
selection, envelope encryption, and
KMS integration to produce the final
encrypted payload.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..registry import AlgorithmRegistry, CryptoAlgorithm
from ..exceptions import CryptoEncryptionError


@dataclass
class EncryptionResult:
    """
    Encryption operation result.

    Attributes:
        ciphertext: Encrypted data (base64 encoded).
        algorithm: Algorithm used.
        key_id: KMS key ID used.
        encrypted_dek: Encrypted data encryption key.
        nonce: Nonce used (if applicable).
        aad: Additional authenticated data.
        metadata: Additional metadata.
    """

    ciphertext: str = ""
    algorithm: str = ""
    key_id: str = ""
    encrypted_dek: str = ""
    nonce: str = ""
    aad: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": self.ciphertext,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "encrypted_dek": self.encrypted_dek,
            "nonce": self.nonce,
            "aad": self.aad,
            "metadata": self.metadata,
        }


class EncryptionPipeline:
    """
    Encryption pipeline orchestrator.

    Manages the encryption workflow including:
    - Algorithm selection
    - Data key generation
    - Envelope encryption
    - KMS key wrapping
    - Result packaging

    Usage:
        pipeline = EncryptionPipeline(
            registry=registry,
            kms_provider=kms,
        )
        result = await pipeline.encrypt(
            data=b"sensitive data",
            key_id="my-key",
        )
    """

    def __init__(
        self,
        registry: AlgorithmRegistry,
        kms_provider: Optional[Any] = None,
        envelope_enabled: bool = True,
    ) -> None:
        """
        Initialize encryption pipeline.

        Args:
            registry: Algorithm registry.
            kms_provider: KMS provider for key wrapping.
            envelope_enabled: Whether to use envelope encryption.
        """
        self._registry = registry
        self._kms_provider = kms_provider
        self._envelope_enabled = envelope_enabled

    async def encrypt(
        self,
        data: bytes,
        key_id: str,
        algorithm_name: Optional[str] = None,
        aad: Optional[bytes] = None,
        **kwargs: Any,
    ) -> EncryptionResult:
        """
        Encrypt data through the pipeline.

        Args:
            data: Plaintext data to encrypt.
            key_id: KMS key ID for DEK encryption.
            algorithm_name: Algorithm to use.
            aad: Additional authenticated data.

        Returns:
            EncryptionResult with encrypted payload.
        """
        try:
            # Step 1: Get algorithm
            algo = self._get_algorithm(algorithm_name)

            if self._envelope_enabled and self._kms_provider:
                # Envelope encryption flow
                return await self._envelope_encrypt(
                    data=data,
                    key_id=key_id,
                    algo=algo,
                    aad=aad,
                    **kwargs,
                )
            else:
                # Direct encryption flow
                return await self._direct_encrypt(
                    data=data,
                    key_id=key_id,
                    algo=algo,
                    aad=aad,
                    **kwargs,
                )
        except CryptoEncryptionError:
            raise
        except Exception as e:
            raise CryptoEncryptionError(
                algorithm=algorithm_name or "default",
                reason=str(e),
            )

    def _get_algorithm(
        self,
        name: Optional[str],
    ) -> CryptoAlgorithm:
        """Get algorithm instance by name."""
        if name:
            return self._registry.get(name)

        # Get default symmetric algorithm
        for algo in self._registry._algorithms.values():
            from ..registry import AsymmetricAlgorithm, HashAlgorithm
            if not isinstance(algo, (AsymmetricAlgorithm, HashAlgorithm)):
                return algo

        # Fallback: return first algorithm
        algorithms = list(self._registry._algorithms.values())
        if not algorithms:
            raise CryptoEncryptionError(
                reason="No encryption algorithm registered",
            )
        return algorithms[0]

    async def _envelope_encrypt(
        self,
        data: bytes,
        key_id: str,
        algo: CryptoAlgorithm,
        aad: Optional[bytes],
        **kwargs: Any,
    ) -> EncryptionResult:
        """Perform envelope encryption."""
        # Generate DEK
        dek = os.urandom(32)

        # Encrypt data with DEK
        nonce = os.urandom(12)
        encrypted_data = await algo.encrypt(
            data=data,
            key=dek,
            nonce=nonce,
            aad=aad,
        )

        # Encrypt DEK with KMS
        encrypted_dek = await self._kms_provider.encrypt_key(
            key_id=key_id,
            data_key=dek,
        )

        return EncryptionResult(
            ciphertext=base64.b64encode(encrypted_data).decode(),
            algorithm=algo.name,
            key_id=key_id,
            encrypted_dek=base64.b64encode(encrypted_dek).decode(),
            nonce=base64.b64encode(nonce).decode(),
            aad=base64.b64encode(aad).decode() if aad else "",
            metadata={
                "mode": "envelope",
                "dek_size": len(dek),
            },
        )

    async def _direct_encrypt(
        self,
        data: bytes,
        key_id: str,
        algo: CryptoAlgorithm,
        aad: Optional[bytes],
        **kwargs: Any,
    ) -> EncryptionResult:
        """Perform direct encryption."""
        # Use the key_id as the key (development mode)
        key = kwargs.get("key")
        if key is None:
            raise CryptoEncryptionError(
                algorithm=algo.name,
                reason="No encryption key provided",
            )

        nonce = os.urandom(12)
        encrypted_data = await algo.encrypt(
            data=data,
            key=key,
            nonce=nonce,
            aad=aad,
        )

        return EncryptionResult(
            ciphertext=base64.b64encode(encrypted_data).decode(),
            algorithm=algo.name,
            key_id=key_id,
            nonce=base64.b64encode(nonce).decode(),
            aad=base64.b64encode(aad).decode() if aad else "",
            metadata={"mode": "direct"},
        )
