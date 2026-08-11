"""
Bloom Filter — probabilistic data structure for efficient existence queries
in the data lake with configurable false positive rates.

Commit 16 Part 1.3
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BloomFilterConfig:
    """Configuration for a Bloom Filter."""
    expected_items: int = 1_000_000
    false_positive_rate: float = 0.01
    hash_count: Optional[int] = None
    bit_size: Optional[int] = None

    def __post_init__(self) -> None:
        if self.bit_size is None:
            n = self.expected_items
            p = self.false_positive_rate
            m = - (n * math.log(p)) / (math.log(2) ** 2)
            self.bit_size = max(1, int(math.ceil(m)))
        if self.hash_count is None:
            k = (self.bit_size / self.expected_items) * math.log(2)
            self.hash_count = max(1, int(round(k)))


class BloomFilter:
    """
    Bloom filter for efficient existence queries in the data lake.

    Used for partition pruning and checking whether a key exists
    before performing a full table scan.

    Features:
    - Configurable false positive rate
    - Multiple hash functions via double hashing
    - Union and intersection operations
    - Serialization and deserialization
    - Cardinality estimation
    """

    def __init__(
        self,
        name: str,
        config: Optional[BloomFilterConfig] = None,
    ) -> None:
        self.name = name
        self.config = config or BloomFilterConfig()
        self._bit_array = bytearray(
            (self.config.bit_size + 7) // 8  # noqa: WPS437
        )
        self._item_count = 0

    def _hash(self, item: Any, seed: int) -> int:
        """Compute a single hash value for the given item and seed."""
        data = f"{item}:{seed}".encode("utf-8")
        digest = hashlib.sha256(data).digest()
        value = int.from_bytes(digest[:8], "big")
        return value % self.config.bit_size

    def add(self, item: Any) -> None:
        """Add an item to the bloom filter."""
        for seed in range(self.config.hash_count):
            bit_index = self._hash(item, seed)
            byte_index = bit_index // 8
            bit_offset = bit_index % 8
            self._bit_array[byte_index] |= (1 << bit_offset)
        self._item_count += 1

    def contains(self, item: Any) -> bool:
        """Check if an item might be in the filter (may produce false positives)."""
        for seed in range(self.config.hash_count):
            bit_index = self._hash(item, seed)
            byte_index = bit_index // 8
            bit_offset = bit_index % 8
            if not (self._bit_array[byte_index] & (1 << bit_offset)):
                return False
        return True

    async def insert_batch(self, items: list[Any]) -> int:
        """Insert a batch of items into the filter."""
        count = 0
        for item in items:
            self.add(item)
            count += 1
        return count

    async def check_batch(self, items: list[Any]) -> dict[Any, bool]:
        """Check a batch of items."""
        return {item: self.contains(item) for item in items}

    def union(self, other: BloomFilter) -> BloomFilter:
        """Create a new filter that is the union of this and another."""
        if self.config.bit_size != other.config.bit_size:
            raise ValueError("Bloom filters must have same bit size for union")
        result = BloomFilter(
            name=f"{self.name}_union_{other.name}",
            config=self.config,
        )
        for i, (a, b) in enumerate(zip(self._bit_array, other._bit_array)):
            result._bit_array[i] = a | b  # noqa: WPS437
        result._item_count = self._item_count + other._item_count  # noqa: WPS437
        return result

    def intersection(self, other: BloomFilter) -> BloomFilter:
        """Create a new filter that is the intersection of this and another."""
        if self.config.bit_size != other.config.bit_size:
            raise ValueError("Bloom filters must have same bit size for intersection")
        result = BloomFilter(
            name=f"{self.name}_intersection_{other.name}",
            config=self.config,
        )
        for i, (a, b) in enumerate(zip(self._bit_array, other._bit_array)):
            result._bit_array[i] = a & b  # noqa: WPS437
        result._item_count = min(self._item_count, other._item_count)  # noqa: WPS437
        return result

    @property
    def estimated_cardinality(self) -> int:
        """Estimate the number of items in the filter."""
        set_bits = sum(bin(b).count("1") for b in self._bit_array)
        m = self.config.bit_size
        k = self.config.hash_count
        if set_bits == 0:
            return 0
        if set_bits >= m:
            return self._item_count
        n = -(m / k) * math.log(1 - set_bits / m)
        return int(round(n))

    @property
    def fill_ratio(self) -> float:
        """Ratio of bits set to total bits."""
        set_bits = sum(bin(b).count("1") for b in self._bit_array)
        return set_bits / self.config.bit_size

    @property
    def size_bytes(self) -> int:
        """Size of the bit array in bytes."""
        return len(self._bit_array)

    async def serialize(self) -> bytes:
        """Serialize the bloom filter to bytes."""
        return bytes(self._bit_array)

    @classmethod
    async def deserialize(cls, name: str, data: bytes, config: BloomFilterConfig) -> BloomFilter:
        """Deserialize a bloom filter from bytes."""
        bf = cls(name=name, config=config)
        bf._bit_array = bytearray(data)  # noqa: WPS437
        return bf

    async def clear(self) -> None:
        """Clear all bits in the filter."""
        self._bit_array = bytearray(len(self._bit_array))
        self._item_count = 0


class BloomFilterManager:
    """
    Manages multiple bloom filters across datasets and columns.

    Features:
    - Per-dataset, per-column bloom filters
    - Automatic filter creation
    - Filter statistics
    - Serialization to/from storage
    - Partition pruning via bloom filter checks
    """

    def __init__(self) -> None:
        self._filters: dict[str, dict[str, BloomFilter]] = {}

    async def get_or_create(
        self,
        dataset: str,
        column: str,
        config: Optional[BloomFilterConfig] = None,
    ) -> BloomFilter:
        """Get an existing bloom filter or create a new one."""
        if dataset not in self._filters:
            self._filters[dataset] = {}

        filter_key = f"{dataset}:{column}"
        if filter_key not in self._filters[dataset]:
            bf = BloomFilter(name=filter_key, config=config)
            self._filters[dataset][filter_key] = bf
            logger.info("Created bloom filter: %s", filter_key)
        return self._filters[dataset][filter_key]

    async def get(self, dataset: str, column: str) -> Optional[BloomFilter]:
        """Get a bloom filter by dataset and column."""
        return self._filters.get(dataset, {}).get(f"{dataset}:{column}")

    async def add_item(self, dataset: str, column: str, item: Any) -> None:
        """Add an item to a bloom filter."""
        bf = await self.get_or_create(dataset, column)
        bf.add(item)

    async def add_batch(
        self, dataset: str, column: str, items: list[Any]
    ) -> int:
        """Add a batch of items to a bloom filter."""
        bf = await self.get_or_create(dataset, column)
        count = await bf.insert_batch(items)
        logger.debug(
            "Added %d items to bloom filter %s:%s", count, dataset, column,
        )
        return count

    async def check(
        self, dataset: str, column: str, item: Any
    ) -> bool:
        """Check if an item might exist in the dataset column."""
        bf = await self.get(dataset, column)
        if bf is None:
            return False
        return bf.contains(item)

    async def check_batch(
        self, dataset: str, column: str, items: list[Any]
    ) -> dict[Any, bool]:
        """Check a batch of items."""
        bf = await self.get(dataset, column)
        if bf is None:
            return {item: False for item in items}
        return await bf.check_batch(items)

    async def list_filters(self) -> list[dict[str, Any]]:
        """List all managed bloom filters with statistics."""
        result = []
        for dataset, filters in self._filters.items():
            for key, bf in filters.items():
                result.append({
                    "dataset": dataset,
                    "key": key,
                    "item_count": bf._item_count,
                    "estimated_cardinality": bf.estimated_cardinality,
                    "fill_ratio": round(bf.fill_ratio, 4),
                    "size_bytes": bf.size_bytes,
                })
        return result

    async def delete_filter(self, dataset: str, column: str) -> bool:
        """Delete a bloom filter."""
        filter_key = f"{dataset}:{column}"
        if dataset in self._filters and filter_key in self._filters[dataset]:
            del self._filters[dataset][filter_key]
            logger.info("Deleted bloom filter: %s", filter_key)
            return True
        return False

    async def clear_dataset(self, dataset: str) -> None:
        """Clear all bloom filters for a dataset."""
        if dataset in self._filters:
            count = len(self._filters[dataset])
            self._filters[dataset].clear()
            logger.info("Cleared %d bloom filters for dataset: %s", count, dataset)

    async def total_filters(self) -> int:
        """Get the total number of managed bloom filters."""
        return sum(len(f) for f in self._filters.values())
