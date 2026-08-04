"""
Algorithm registry.

Provides a registry for cryptographic
algorithm implementations, enabling
dynamic algorithm discovery and
selection at runtime.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .constants import AlgorithmName, ALGORITHM_DEFAULTS
from .exceptions import CryptoAlgorithmNotSupportedError

logger = logging.getLogger(__name__)


class CryptoAlgorithm(ABC):
    """
    Base class for cryptographic algorithm implementations.

    All algorithm implementations must
    inherit from this class and implement
    the required methods.

    Usage:
        class MyAlgorithm(CryptoAlgorithm):
            name = "my-algo"
            async def encrypt(self, data, key, **kwargs):
                ...
    """

    name: str = ""
    version: str = "1.0.0"

    @abstractmethod
    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Encrypt data using the algorithm.

        Args:
            data: Plaintext data to encrypt.
            key: Encryption key.
            **kwargs: Algorithm-specific parameters.

        Returns:
            Encrypted ciphertext.
        """
        ...

    @abstractmethod
    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Decrypt data using the algorithm.

        Args:
            ciphertext: Ciphertext to decrypt.
            key: Decryption key.
            **kwargs: Algorithm-specific parameters.

        Returns:
            Decrypted plaintext.
        """
        ...

    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for this algorithm."""
        return ALGORITHM_DEFAULTS.get(self.name, {})

    def get_info(self) -> Dict[str, Any]:
        """Get algorithm information."""
        return {
            "name": self.name,
            "version": self.version,
            "defaults": self.get_default_params(),
        }


class AsymmetricAlgorithm(CryptoAlgorithm):
    """
    Base class for asymmetric (public-key) algorithms.

    Extends CryptoAlgorithm with sign/verify
    capabilities for public-key cryptography.
    """

    @abstractmethod
    async def sign(
        self,
        data: bytes,
        private_key: Any,
        **kwargs: Any,
    ) -> bytes:
        """
        Sign data with a private key.

        Args:
            data: Data to sign.
            private_key: Private key object or bytes.
            **kwargs: Algorithm-specific parameters.

        Returns:
            Signature bytes.
        """
        ...

    @abstractmethod
    async def verify(
        self,
        data: bytes,
        signature: bytes,
        public_key: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Verify a signature with a public key.

        Args:
            data: Original data.
            signature: Signature to verify.
            public_key: Public key object or bytes.
            **kwargs: Algorithm-specific parameters.

        Returns:
            True if signature is valid.
        """
        ...


class HashAlgorithm(CryptoAlgorithm):
    """
    Base class for hash algorithms.

    Provides hashing functionality
    without encryption/decryption.
    """

    @abstractmethod
    async def compute_hash(
        self,
        data: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Compute hash of data.

        Args:
            data: Data to hash.
            **kwargs: Algorithm-specific parameters.

        Returns:
            Hash digest.
        """
        ...

    # Override: encrypt/decrypt are no-ops for hash algorithms
    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return data

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return ciphertext


class HMACAlgorithm(CryptoAlgorithm):
    """
    Base class for HMAC algorithms.

    Provides HMAC computation and
    verification capabilities.
    """

    @abstractmethod
    async def compute_hmac(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Compute HMAC of data.

        Args:
            data: Data to authenticate.
            key: HMAC key.
            **kwargs: Algorithm-specific parameters.

        Returns:
            HMAC digest.
        """
        ...

    async def verify_hmac(
        self,
        data: bytes,
        key: bytes,
        expected_hmac: bytes,
        **kwargs: Any,
    ) -> bool:
        """
        Verify HMAC integrity.

        Args:
            data: Original data.
            key: HMAC key.
            expected_hmac: Expected HMAC value.
            **kwargs: Algorithm-specific parameters.

        Returns:
            True if HMAC matches.
        """
        import hmac as _hmac
        computed = await self.compute_hmac(data, key, **kwargs)
        return _hmac.compare_digest(computed, expected_hmac)

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return data

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return ciphertext


class PasswordHashAlgorithm(CryptoAlgorithm):
    """
    Base class for password hashing algorithms.

    Provides password hashing with
    built-in salt generation and
    verification.
    """

    @abstractmethod
    async def hash_password(
        self,
        password: str,
        **kwargs: Any,
    ) -> str:
        """
        Hash a password.

        Args:
            password: Plaintext password.
            **kwargs: Algorithm-specific parameters.

        Returns:
            Hashed password string.
        """
        ...

    @abstractmethod
    async def verify_password(
        self,
        password: str,
        hash_value: str,
        **kwargs: Any,
    ) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plaintext password.
            hash_value: Stored hash value.
            **kwargs: Algorithm-specific parameters.

        Returns:
            True if password matches.
        """
        ...

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return data

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        return ciphertext


class AlgorithmRegistry:
    """
    Registry for cryptographic algorithms.

    Manages algorithm implementations and
    provides lookup by name, type, or capability.

    Usage:
        registry = AlgorithmRegistry()
        registry.register(AES256GCM())
        algo = registry.get("aes-256-gcm")
        result = await algo.encrypt(data, key)
    """

    def __init__(self) -> None:
        self._algorithms: Dict[str, CryptoAlgorithm] = {}
        self._type_index: Dict[str, List[str]] = {
            "symmetric": [],
            "asymmetric": [],
            "hash": [],
            "hmac": [],
            "password": [],
        }

    def register(self, algorithm: CryptoAlgorithm) -> None:
        """
        Register an algorithm implementation.

        Args:
            algorithm: Algorithm instance to register.

        Raises:
            ValueError: If algorithm name is already registered.
        """
        name = algorithm.name
        if not name:
            raise ValueError("Algorithm must have a name")

        self._algorithms[name] = algorithm

        # Index by type
        algo_type = self._classify_algorithm(algorithm)
        if algo_type not in self._type_index:
            self._type_index[algo_type] = []
        if name not in self._type_index[algo_type]:
            self._type_index[algo_type].append(name)

        logger.debug(
            "Algorithm registered: %s (type=%s)", name, algo_type,
        )

    def get(
        self,
        name: str,
    ) -> CryptoAlgorithm:
        """
        Get an algorithm by name.

        Args:
            name: Algorithm name.

        Returns:
            Algorithm instance.

        Raises:
            CryptoAlgorithmNotSupportedError: If not found.
        """
        algo = self._algorithms.get(name)
        if algo is None:
            raise CryptoAlgorithmNotSupportedError(name)
        return algo

    def get_for_operation(
        self,
        operation: str,
        preferred_name: Optional[str] = None,
    ) -> CryptoAlgorithm:
        """
        Get the best algorithm for an operation.

        Args:
            operation: Operation type (encrypt, decrypt, sign, etc.).
            preferred_name: Preferred algorithm name.

        Returns:
            Algorithm instance.
        """
        if preferred_name:
            return self.get(preferred_name)

        # Return first registered algorithm
        if not self._algorithms:
            raise CryptoAlgorithmNotSupportedError("")

        return next(iter(self._algorithms.values()))

    def list_algorithms(self) -> List[Dict[str, Any]]:
        """List all registered algorithms."""
        return [
            algo.get_info() for algo in self._algorithms.values()
        ]

    def list_by_type(self, algo_type: str) -> List[str]:
        """List algorithm names by type."""
        return self._type_index.get(algo_type, [])

    def is_supported(self, name: str) -> bool:
        """Check if an algorithm is supported."""
        return name in self._algorithms

    def unregister(self, name: str) -> bool:
        """Unregister an algorithm."""
        algo = self._algorithms.pop(name, None)
        if algo is None:
            return False

        algo_type = self._classify_algorithm(algo)
        if name in self._type_index.get(algo_type, []):
            self._type_index[algo_type].remove(name)
        return True

    def count(self) -> int:
        """Get number of registered algorithms."""
        return len(self._algorithms)

    def _classify_algorithm(self, algo: CryptoAlgorithm) -> str:
        """Classify an algorithm by its interface."""
        if isinstance(algo, AsymmetricAlgorithm):
            return "asymmetric"
        if isinstance(algo, HMACAlgorithm):
            return "hmac"
        if isinstance(algo, HashAlgorithm):
            return "hash"
        if isinstance(algo, PasswordHashAlgorithm):
            return "password"
        return "symmetric"

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_algorithms": len(self._algorithms),
            "algorithms": list(self._algorithms.keys()),
            "by_type": {
                k: len(v) for k, v in self._type_index.items()
            },
        }
