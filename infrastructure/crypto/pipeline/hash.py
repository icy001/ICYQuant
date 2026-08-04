"""
Hash pipeline.

Orchestrates hashing and HMAC
operations including algorithm
selection, computation, and
verification for data integrity
and authentication.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..registry import (
    AlgorithmRegistry,
    HashAlgorithm,
    HMACAlgorithm,
    PasswordHashAlgorithm,
)
from ..exceptions import CryptoHashError


@dataclass
class HashResult:
    """
    Hash operation result.

    Attributes:
        digest: Computed hash digest (base64).
        algorithm: Algorithm used.
        metadata: Additional metadata.
    """

    digest: str = ""
    algorithm: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "digest": self.digest,
            "algorithm": self.algorithm,
            "metadata": self.metadata,
        }


@dataclass
class HMACResult:
    """
    HMAC operation result.

    Attributes:
        digest: Computed HMAC digest (base64).
        algorithm: Algorithm used.
        metadata: Additional metadata.
    """

    digest: str = ""
    algorithm: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class HashPipeline:
    """
    Hash and HMAC pipeline orchestrator.

    Manages hashing workflows including:
    - Algorithm selection
    - Hash computation
    - HMAC computation
    - Password hashing
    - Integrity verification

    Usage:
        pipeline = HashPipeline(registry=registry)
        result = await pipeline.hash(b"data")
        hmac_result = await pipeline.hmac(b"data", b"key")
    """

    def __init__(self, registry: AlgorithmRegistry) -> None:
        self._registry = registry

    async def hash(
        self,
        data: bytes,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> HashResult:
        """
        Compute hash of data.

        Args:
            data: Data to hash.
            algorithm_name: Hash algorithm to use.

        Returns:
            HashResult with computed digest.
        """
        try:
            algo = self._get_hash_algorithm(algorithm_name)
            digest = await algo.compute_hash(data, **kwargs)

            return HashResult(
                digest=base64.b64encode(digest).decode(),
                algorithm=algo.name,
                metadata={"data_size": len(data)},
            )
        except Exception as e:
            raise CryptoHashError(f"Hash computation failed: {e}")

    async def hmac(
        self,
        data: bytes,
        key: bytes,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> HMACResult:
        """
        Compute HMAC of data.

        Args:
            data: Data to authenticate.
            key: HMAC key.
            algorithm_name: HMAC algorithm to use.

        Returns:
            HMACResult with computed digest.
        """
        try:
            algo = self._get_hmac_algorithm(algorithm_name)
            digest = await algo.compute_hmac(data, key, **kwargs)

            return HMACResult(
                digest=base64.b64encode(digest).decode(),
                algorithm=algo.name,
                metadata={"data_size": len(data)},
            )
        except Exception as e:
            raise CryptoHashError(f"HMAC computation failed: {e}")

    async def verify_hmac(
        self,
        data: bytes,
        key: bytes,
        expected_hmac: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Verify HMAC integrity.

        Args:
            data: Original data.
            key: HMAC key.
            expected_hmac: Expected HMAC (base64).
            algorithm_name: HMAC algorithm.

        Returns:
            True if HMAC matches.
        """
        try:
            algo = self._get_hmac_algorithm(algorithm_name)
            expected = base64.b64decode(expected_hmac)
            return await algo.verify_hmac(data, key, expected, **kwargs)
        except Exception:
            return False

    async def hash_password(
        self,
        password: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Hash a password for storage.

        Args:
            password: Plaintext password.
            algorithm_name: Password hash algorithm.

        Returns:
            Hashed password string.
        """
        try:
            algo = self._get_password_algorithm(algorithm_name)
            return await algo.hash_password(password, **kwargs)
        except Exception as e:
            raise CryptoHashError(f"Password hashing failed: {e}")

    async def verify_password(
        self,
        password: str,
        hash_value: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plaintext password.
            hash_value: Stored hash.
            algorithm_name: Password hash algorithm.

        Returns:
            True if password matches.
        """
        try:
            algo = self._get_password_algorithm(algorithm_name)
            return await algo.verify_password(password, hash_value, **kwargs)
        except Exception:
            return False

    def _get_hash_algorithm(
        self,
        name: Optional[str],
    ) -> HashAlgorithm:
        """Get hash algorithm."""
        if name:
            algo = self._registry.get(name)
            if isinstance(algo, HashAlgorithm):
                return algo
            raise CryptoHashError(f"Algorithm {name} is not a hash algorithm")

        for algo in self._registry._algorithms.values():
            if isinstance(algo, HashAlgorithm):
                return algo

        raise CryptoHashError("No hash algorithm registered")

    def _get_hmac_algorithm(
        self,
        name: Optional[str],
    ) -> HMACAlgorithm:
        """Get HMAC algorithm."""
        if name:
            algo = self._registry.get(name)
            if isinstance(algo, HMACAlgorithm):
                return algo
            raise CryptoHashError(f"Algorithm {name} is not an HMAC algorithm")

        for algo in self._registry._algorithms.values():
            if isinstance(algo, HMACAlgorithm):
                return algo

        raise CryptoHashError("No HMAC algorithm registered")

    def _get_password_algorithm(
        self,
        name: Optional[str],
    ) -> PasswordHashAlgorithm:
        """Get password hash algorithm."""
        if name:
            algo = self._registry.get(name)
            if isinstance(algo, PasswordHashAlgorithm):
                return algo
            raise CryptoHashError(
                f"Algorithm {name} is not a password hash algorithm",
            )

        for algo in self._registry._algorithms.values():
            if isinstance(algo, PasswordHashAlgorithm):
                return algo

        raise CryptoHashError("No password hash algorithm registered")
