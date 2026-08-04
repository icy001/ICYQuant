"""
Rollout consistent hashing engine.

Provides stable, deterministic, cross-platform
hashing algorithms for percentage-based rollout.
Supports MurmurHash3, SHA-256, and CRC32
for different balance-speed tradeoffs.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Optional


# MurmurHash3 implementation (32-bit)
# This is a faithful port of the public domain MurmurHash3
# by Austin Appleby. Optimized for Python 3.9+.

def _murmurhash3_32(data: bytes, seed: int = 0) -> int:
    """
    Compute MurmurHash3 32-bit hash.

    Args:
        data: Input bytes.
        seed: Seed value.

    Returns:
        32-bit integer hash value.
    """
    c1 = 0xcc9e2d51
    c2 = 0x1b873593
    length = len(data)
    h1 = seed
    roundedEnd = length & 0xfffffffc

    for i in range(0, roundedEnd, 4):
        k1 = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)
        k1 = (k1 * c1) & 0xffffffff
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xffffffff
        k1 = (k1 * c2) & 0xffffffff
        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xffffffff
        h1 = (h1 * 5 + 0xe6546b64) & 0xffffffff

    k1 = 0
    val = length & 0x03
    if val == 3:
        k1 = data[roundedEnd + 2] << 16
    if val in (2, 3):
        k1 |= data[roundedEnd + 1] << 8
    if val in (1, 2, 3):
        k1 |= data[roundedEnd]
        k1 = (k1 * c1) & 0xffffffff
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xffffffff
        k1 = (k1 * c2) & 0xffffffff
        h1 ^= k1

    h1 ^= length
    h1 ^= (h1 >> 16)
    h1 = (h1 * 0x85ebca6b) & 0xffffffff
    h1 ^= (h1 >> 13)
    h1 = (h1 * 0xc2b2ae35) & 0xffffffff
    h1 ^= (h1 >> 16)
    return h1


class ConsistentHasher:
    """
    Stable, deterministic hash engine for percentage rollouts.

    Provides multiple hash algorithms with different
    characteristics:
        - murmur3: Fast, good distribution, 32-bit
        - sha256: Cryptographic strength, 256-bit
        - crc32: Fast checksum, good for low-collision needs

    The same input always produces the same output
    regardless of platform, making it safe for
    distributed systems and audit trails.

    Usage:
        hasher = ConsistentHasher(algorithm="murmur3")
        bucket = hasher.hash_to_bucket("feature:account_123", 10000)
        # Returns stable bucket in [0, 10000)
    """

    ALGORITHMS = ("murmur3", "sha256", "crc32")

    def __init__(
        self,
        algorithm: str = "murmur3",
        seed: int = 0,
    ) -> None:
        """
        Initialize the consistent hasher.

        Args:
            algorithm: Hash algorithm ("murmur3", "sha256", "crc32").
            seed: Seed for the hash function.

        Raises:
            ValueError: If algorithm is not supported.
        """
        if algorithm not in self.ALGORITHMS:
            raise ValueError(
                f"Unsupported algorithm: {algorithm}. "
                f"Choose from: {', '.join(self.ALGORITHMS)}",
            )
        self._algorithm = algorithm
        self._seed = seed
        self._cache: dict[str, int] = {}

    def hash(self, key: str) -> int:
        """
        Compute a hash value for the given key.

        Args:
            key: Input string to hash.

        Returns:
            Raw hash value (unsigned 32-bit range).
        """
        if key in self._cache:
            return self._cache[key]

        result = self._compute_hash(key)
        self._cache[key] = result
        return result

    def hash_to_bucket(
        self,
        key: str,
        max_buckets: int = 10000,
    ) -> int:
        """
        Map a key to a bucket in [0, max_buckets).

        This is the primary method for percentage
        rollouts: bucket < percentage * max_buckets
        means the target falls within the rollout.

        Args:
            key: Input key (e.g. "feature:account_123").
            max_buckets: Total number of buckets.

        Returns:
            Bucket index in range [0, max_buckets).
        """
        raw = self.hash(key)
        return raw % max_buckets

    def is_in_rollout(
        self,
        key: str,
        percentage: float,
        max_buckets: int = 10000,
    ) -> bool:
        """
        Check if a key falls within a percentage rollout.

        Args:
            key: Input key (e.g. "feature:account_123").
            percentage: Rollout percentage (0.0 - 100.0).
            max_buckets: Total number of buckets.

        Returns:
            True if the key is in the rollout.
        """
        bucket = self.hash_to_bucket(key, max_buckets)
        threshold = int(percentage * max_buckets / 100.0)
        return bucket < threshold

    def _compute_hash(self, key: str) -> int:
        """Compute the hash value using the selected algorithm."""
        data = key.encode("utf-8")

        if self._algorithm == "murmur3":
            return _murmurhash3_32(data, self._seed)

        elif self._algorithm == "sha256":
            digest = hashlib.sha256(data).digest()
            return struct.unpack("<I", digest[:4])[0]

        elif self._algorithm == "crc32":
            return zlib.crc32(data, self._seed) & 0xffffffff

        # Fallback (should never happen due to init validation)
        return 0

    def clear_cache(self) -> None:
        """Clear the hash cache."""
        self._cache.clear()

    @property
    def algorithm(self) -> str:
        """Get the current algorithm name."""
        return self._algorithm

    @property
    def cache_size(self) -> int:
        """Get the number of cached hashes."""
        return len(self._cache)


def compute_hash(
    key: str,
    algorithm: str = "murmur3",
    max_buckets: int = 10000,
    seed: int = 0,
) -> int:
    """
    Convenience function to compute a hash bucket.

    Args:
        key: Input key.
        algorithm: Hash algorithm.
        max_buckets: Total buckets.
        seed: Seed value.

    Returns:
        Bucket index.
    """
    hasher = ConsistentHasher(algorithm=algorithm, seed=seed)
    return hasher.hash_to_bucket(key, max_buckets)


def is_in_percentage_rollout(
    flag_key: str,
    target_id: str,
    percentage: float,
    algorithm: str = "murmur3",
    hash_key: str = "",
) -> bool:
    """
    Check if a target falls within a percentage rollout.

    Args:
        flag_key: Feature flag key.
        target_id: Target identifier.
        percentage: Rollout percentage (0-100).
        algorithm: Hash algorithm to use.
        hash_key: Hash dimension (overrides target_id if provided).

    Returns:
        True if the target is in the rollout.
    """
    key = hash_key or target_id
    combined = f"{flag_key}:{key}"
    hasher = ConsistentHasher(algorithm=algorithm)
    return hasher.is_in_rollout(combined, percentage)
