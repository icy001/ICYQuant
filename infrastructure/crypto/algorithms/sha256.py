"""
SHA-256 and SHA-512 hash algorithms.

Implements secure hashing for
data integrity verification,
content addressing, and
checksum computation.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoHashError
from ..registry import HashAlgorithm

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import utils
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class SHA256(HashAlgorithm):
    """
    SHA-256 hash algorithm.

    Provides 256-bit cryptographic
    hashing for data integrity,
    fingerprinting, and content
    addressing.
    """

    name: str = AlgorithmName.SHA_256.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._hash_size = 32

    async def compute_hash(
        self,
        data: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Compute SHA-256 hash.

        Args:
            data: Data to hash.

        Returns:
            32-byte hash digest.
        """
        try:
            if _HAS_CRYPTO:
                digest = hashes.Hash(hashes.SHA256())
                digest.update(data)
                return digest.finalize()
            else:
                return hashlib.sha256(data).digest()
        except Exception as e:
            raise CryptoHashError(f"SHA-256 hashing failed: {e}")

    def get_default_params(self) -> Dict[str, Any]:
        return {"hash_size": self._hash_size}


class SHA512(HashAlgorithm):
    """
    SHA-512 hash algorithm.

    Provides 512-bit cryptographic
    hashing for applications requiring
    higher collision resistance.
    """

    name: str = AlgorithmName.SHA_512.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._hash_size = 64

    async def compute_hash(
        self,
        data: bytes,
        **kwargs: Any,
    ) -> bytes:
        try:
            if _HAS_CRYPTO:
                digest = hashes.Hash(hashes.SHA512())
                digest.update(data)
                return digest.finalize()
            else:
                return hashlib.sha512(data).digest()
        except Exception as e:
            raise CryptoHashError(f"SHA-512 hashing failed: {e}")

    def get_default_params(self) -> Dict[str, Any]:
        return {"hash_size": self._hash_size}
