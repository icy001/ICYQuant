"""
HMAC algorithm implementations.

Implements HMAC-SHA256 and HMAC-SHA512
for message authentication using
the cryptography library.
"""

from __future__ import annotations

import hmac as _hmac
import hashlib
from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoHashError
from ..registry import HMACAlgorithm

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.hmac import HMAC as _HMAC
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class HMACSHA256(HMACAlgorithm):
    """
    HMAC-SHA256 message authentication.

    Provides Hash-based Message
    Authentication Code using SHA-256,
    suitable for API authentication,
    webhook verification, and
    data integrity checks.
    """

    name: str = AlgorithmName.HMAC_SHA256.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._hash_size = 32
        self._key_size = 32

    async def compute_hmac(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Compute HMAC-SHA256.

        Args:
            data: Data to authenticate.
            key: HMAC key.

        Returns:
            32-byte HMAC digest.
        """
        try:
            if _HAS_CRYPTO:
                h = _HMAC(key, hashes.SHA256())
                h.update(data)
                return h.finalize()
            else:
                return _hmac.new(key, data, hashlib.sha256).digest()
        except Exception as e:
            raise CryptoHashError(f"HMAC-SHA256 computation failed: {e}")

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "hash_size": self._hash_size,
            "key_size": self._key_size,
        }


class HMACSHA512(HMACAlgorithm):
    """
    HMAC-SHA512 message authentication.

    Provides stronger 512-bit HMAC
    for high-security applications.
    """

    name: str = AlgorithmName.HMAC_SHA512.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._hash_size = 64
        self._key_size = 64

    async def compute_hmac(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        try:
            if _HAS_CRYPTO:
                h = _HMAC(key, hashes.SHA512())
                h.update(data)
                return h.finalize()
            else:
                return _hmac.new(key, data, hashlib.sha512).digest()
        except Exception as e:
            raise CryptoHashError(f"HMAC-SHA512 computation failed: {e}")

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "hash_size": self._hash_size,
            "key_size": self._key_size,
        }
