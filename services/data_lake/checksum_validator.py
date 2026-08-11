"""
Checksum Validator — data integrity verification for the data lake
with configurable algorithms and batch validation.

Commit 16 Part 1.3
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChecksumAlgorithm(str, Enum):
    """Supported checksum algorithms."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    XXH64 = "xxh64"
    CRC32 = "crc32"


@dataclass
class ChecksumRecord:
    """A recorded checksum for data integrity verification."""
    record_id: str
    algorithm: ChecksumAlgorithm
    checksum: str
    file_path: str = ""
    dataset: str = ""
    partition: str = ""
    version_id: str = ""
    file_size_bytes: int = 0
    row_count: int = 0
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    verified_at: Optional[datetime] = None
    is_valid: Optional[bool] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChecksumValidator:
    """
    Validates data integrity through checksum verification.

    Supports multiple hash algorithms for different use cases:
    - SHA256: Default for general integrity
    - BLAKE2b: High-performance alternative
    - XXH64: Fast non-cryptographic hashing
    - CRC32: Lightweight corruption detection

    Features:
    - Multi-algorithm checksum computation
    - Batch validation
    - Historical checksum tracking
    - Tamper detection
    - Integrity report generation

    Usage::

        validator = ChecksumValidator()
        record = await validator.compute(data, "us_equity_2024.parquet")
        is_valid = await validator.verify("us_equity_2024.parquet", data)
    """

    def __init__(
        self,
        default_algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256,
    ) -> None:
        self.default_algorithm = default_algorithm
        self._records: dict[str, ChecksumRecord] = {}

    @staticmethod
    def _compute_hash(
        data: bytes, algorithm: ChecksumAlgorithm
    ) -> str:
        """Compute a hash for the given data."""
        if algorithm == ChecksumAlgorithm.MD5:
            return hashlib.md5(data).hexdigest()
        elif algorithm == ChecksumAlgorithm.SHA1:
            return hashlib.sha1(data).hexdigest()
        elif algorithm == ChecksumAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algorithm == ChecksumAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif algorithm == ChecksumAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).hexdigest()
        elif algorithm == ChecksumAlgorithm.CRC32:
            import zlib
            return format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
        elif algorithm == ChecksumAlgorithm.XXH64:
            try:
                import xxhash
                return xxhash.xxh64(data).hexdigest()
            except ImportError:
                logger.warning("xxhash not installed, falling back to SHA256")
                return hashlib.sha256(data).hexdigest()
        else:
            return hashlib.sha256(data).hexdigest()

    async def compute(
        self,
        data: bytes,
        file_path: str,
        *,
        algorithm: Optional[ChecksumAlgorithm] = None,
        dataset: str = "",
        partition: str = "",
        version_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> ChecksumRecord:
        """Compute a checksum for data and record it."""
        algo = algorithm or self.default_algorithm
        checksum = self._compute_hash(data, algo)

        import uuid
        record_id = str(uuid.uuid4())

        record = ChecksumRecord(
            record_id=record_id,
            algorithm=algo,
            checksum=checksum,
            file_path=file_path,
            dataset=dataset,
            partition=partition,
            version_id=version_id,
            file_size_bytes=len(data),
            metadata=metadata or {},
        )
        self._records[record_id] = record

        logger.debug(
            "Checksum computed: %s[%s] file=%s size=%d",
            checksum[:16], algo.value, file_path, len(data),
        )
        return record

    async def verify(
        self,
        file_path: str,
        data: bytes,
        *,
        expected_record_id: Optional[str] = None,
    ) -> bool:
        """Verify data against a previously computed checksum.

        If expected_record_id is provided, verify against that specific record.
        Otherwise, find the latest record for the file path.
        """
        if expected_record_id:
            record = self._records.get(expected_record_id)
        else:
            # Find latest record for file path
            matching = [
                r for r in self._records.values()
                if r.file_path == file_path
            ]
            if not matching:
                logger.warning("No checksum record found for: %s", file_path)
                return False
            record = max(matching, key=lambda r: r.computed_at)

        if record is None:
            return False

        computed = self._compute_hash(data, record.algorithm)
        is_valid = computed == record.checksum
        record.verified_at = datetime.now(timezone.utc)
        record.is_valid = is_valid

        if is_valid:
            logger.debug("Checksum verified: %s", file_path)
        else:
            logger.error(
                "Checksum mismatch for %s: expected=%s, got=%s",
                file_path, record.checksum[:16], computed[:16],
            )
        return is_valid

    async def verify_batch(
        self, items: list[tuple[str, bytes]]
    ) -> dict[str, bool]:
        """Verify a batch of files against their recorded checksums."""
        results: dict[str, bool] = {}
        for file_path, data in items:
            results[file_path] = await self.verify(file_path, data)
        return results

    async def get_record(self, record_id: str) -> Optional[ChecksumRecord]:
        """Get a checksum record by ID."""
        return self._records.get(record_id)

    async def get_records_for_file(self, file_path: str) -> list[ChecksumRecord]:
        """Get all checksum records for a file."""
        return [r for r in self._records.values() if r.file_path == file_path]

    async def get_records_for_dataset(self, dataset: str) -> list[ChecksumRecord]:
        """Get all checksum records for a dataset."""
        return [r for r in self._records.values() if r.dataset == dataset]

    async def list_records(self) -> list[dict[str, Any]]:
        """List all checksum records."""
        return [
            {
                "record_id": r.record_id,
                "file_path": r.file_path,
                "dataset": r.dataset,
                "algorithm": r.algorithm.value,
                "checksum": r.checksum[:16],
                "is_valid": r.is_valid,
                "computed_at": r.computed_at.isoformat(),
            }
            for r in self._records.values()
        ]

    async def integrity_report(self) -> dict[str, Any]:
        """Generate an integrity report for all records."""
        total = len(self._records)
        verified = sum(1 for r in self._records.values() if r.verified_at is not None)
        valid = sum(1 for r in self._records.values() if r.is_valid is True)
        invalid = sum(1 for r in self._records.values() if r.is_valid is False)
        unverified = total - verified

        return {
            "total_records": total,
            "verified": verified,
            "valid": valid,
            "invalid": invalid,
            "unverified": unverified,
            "health_status": "healthy" if invalid == 0 else "corrupted",
            "algorithm_distribution": {
                algo.value: sum(1 for r in self._records.values() if r.algorithm == algo)
                for algo in ChecksumAlgorithm
                if sum(1 for r in self._records.values() if r.algorithm == algo) > 0
            },
        }

    async def delete_record(self, record_id: str) -> bool:
        """Delete a checksum record."""
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

    async def clear_dataset(self, dataset: str) -> int:
        """Clear all checksum records for a dataset."""
        to_remove = [
            rid for rid, r in self._records.items()
            if r.dataset == dataset
        ]
        for rid in to_remove:
            del self._records[rid]
        return len(to_remove)
