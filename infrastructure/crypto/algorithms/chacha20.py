"""
ChaCha20-Poly1305 symmetric encryption.

Implements ChaCha20-Poly1305 authenticated
encryption using the cryptography library,
providing an alternative to AES for
use cases where AES hardware acceleration
is not available.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoDecryptionError, CryptoEncryptionError
from ..registry import CryptoAlgorithm

try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as _ChaCha20Poly1305
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class ChaCha20Poly1305(CryptoAlgorithm):
    """
    ChaCha20-Poly1305 authenticated encryption.

    Provides 256-key ChaCha20 stream cipher
    with Poly1305 authentication, offering
    constant-time execution resistance to
    timing attacks.

    Features:
    - 256-bit key length
    - 12-byte nonces
    - 16-byte authentication tags
    - Constant-time execution
    """

    name: str = AlgorithmName.CHACHA20_POLY1305.value
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
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            if len(key) != self._key_size:
                raise CryptoEncryptionError(
                    algorithm=self.name,
                    reason=f"Invalid key size: {len(key)}",
                )

            nonce = kwargs.get("nonce")
            if nonce is None:
                nonce = os.urandom(self._nonce_size)
            elif len(nonce) != self._nonce_size:
                raise CryptoEncryptionError(
                    algorithm=self.name,
                    reason=f"Invalid nonce size: {len(nonce)}",
                )

            cipher = _ChaCha20Poly1305(key)
            aad = kwargs.get("aad", None)
            ciphertext = cipher.encrypt(nonce, data, aad)

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
        if not _HAS_CRYPTO:
            raise CryptoDecryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            if len(key) != self._key_size:
                raise CryptoDecryptionError(
                    algorithm=self.name,
                    reason=f"Invalid key size: {len(key)}",
                )

            if len(ciphertext) <= self._nonce_size:
                raise CryptoDecryptionError(
                    algorithm=self.name,
                    reason="Ciphertext too short",
                )

            nonce = ciphertext[:self._nonce_size]
            encrypted_data = ciphertext[self._nonce_size:]

            cipher = _ChaCha20Poly1305(key)
            aad = kwargs.get("aad", None)
            plaintext = cipher.decrypt(nonce, encrypted_data, aad)

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
