"""
AES-256-GCM symmetric encryption.

Implements AES-256-GCM authenticated
encryption using the cryptography library,
providing both confidentiality and
integrity verification.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoDecryptionError, CryptoEncryptionError
from ..registry import CryptoAlgorithm

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class AES256GCM(CryptoAlgorithm):
    """
    AES-256-GCM authenticated encryption.

    Provides 256-bit AES encryption with
    12-byte nonces and 16-byte authentication
    tags for authenticated encryption.

    Features:
    - 256-bit key length
    - 12-byte (96-bit) nonces
    - 16-byte authentication tags
    - Associated data support
    """

    name: str = AlgorithmName.AES_256_GCM.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._key_size = 32
        self._nonce_size = 12
        self._tag_size = 16

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Encrypt data with AES-256-GCM.

        Args:
            data: Plaintext data.
            key: 256-bit encryption key.
            **kwargs:
                nonce: Optional nonce (generated if not provided).
                aad: Additional authenticated data.

        Returns:
            Nonce + ciphertext + tag (nonce prepended).
        """
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            if len(key) != self._key_size:
                raise CryptoEncryptionError(
                    algorithm=self.name,
                    reason=f"Invalid key size: {len(key)} bytes, expected {self._key_size}",
                )

            nonce = kwargs.get("nonce")
            if nonce is None:
                nonce = os.urandom(self._nonce_size)
            elif len(nonce) != self._nonce_size:
                raise CryptoEncryptionError(
                    algorithm=self.name,
                    reason=f"Invalid nonce size: {len(nonce)}, expected {self._nonce_size}",
                )

            aesgcm = AESGCM(key)
            aad = kwargs.get("aad", None)
            ciphertext = aesgcm.encrypt(nonce, data, aad)

            return nonce + ciphertext

        except CryptoEncryptionError:
            raise
        except Exception as e:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason=str(e),
            )

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Decrypt AES-256-GCM ciphertext.

        Args:
            ciphertext: Nonce + ciphertext + tag.
            key: 256-bit decryption key.
            **kwargs:
                aad: Additional authenticated data.

        Returns:
            Decrypted plaintext.
        """
        if not _HAS_CRYPTO:
            raise CryptoDecryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            if len(key) != self._key_size:
                raise CryptoDecryptionError(
                    algorithm=self.name,
                    reason=f"Invalid key size: {len(key)} bytes",
                )

            if len(ciphertext) <= self._nonce_size:
                raise CryptoDecryptionError(
                    algorithm=self.name,
                    reason="Ciphertext too short",
                )

            nonce = ciphertext[:self._nonce_size]
            encrypted_data = ciphertext[self._nonce_size:]

            aesgcm = AESGCM(key)
            aad = kwargs.get("aad", None)
            plaintext = aesgcm.decrypt(nonce, encrypted_data, aad)

            return plaintext

        except CryptoDecryptionError:
            raise
        except Exception as e:
            raise CryptoDecryptionError(
                algorithm=self.name,
                reason=str(e),
            )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "key_size": self._key_size,
            "nonce_size": self._nonce_size,
            "tag_size": self._tag_size,
        }
