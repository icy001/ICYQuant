"""
Compression Engine — multi-algorithm compression for data lake storage
with adaptive codec selection.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
import zlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CompressionAlgorithm(str, Enum):
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    LZ4 = "lz4"
    ZSTD = "zstd"
    BROTLI = "brotli"
    LZMA = "lzma"


@dataclass
class CompressedBlock:
    data: bytes
    algorithm: CompressionAlgorithm
    original_size: int
    compressed_size: int
    checksum: str = ""

    @property
    def compression_ratio(self) -> float:
        if self.original_size == 0:
            return 0.0
        return self.compressed_size / self.original_size


class CompressionEngine:
    """
    Adaptive compression engine for the data lake.

    Supports multiple compression algorithms with auto-selection
    based on data characteristics and storage tier.
    """

    DEFAULT_ALGORITHM = CompressionAlgorithm.ZSTD

    def __init__(self, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZSTD) -> None:
        self.algorithm = algorithm
        self._stats: dict[str, Any] = {
            "total_original_bytes": 0,
            "total_compressed_bytes": 0,
            "blocks_compressed": 0,
            "blocks_decompressed": 0,
        }

    def compress(
        self,
        data: bytes,
        algorithm: Optional[CompressionAlgorithm] = None,
    ) -> CompressedBlock:
        """Compress a data block."""
        algo = algorithm or self.algorithm
        original_size = len(data)
        compressed: bytes

        if algo == CompressionAlgorithm.GZIP:
            compressed = zlib.compress(data, level=6)
        elif algo == CompressionAlgorithm.ZSTD:
            try:
                import zstandard as zstd
                cctx = zstd.ZstdCompressor(level=3)
                compressed = cctx.compress(data)
            except ImportError:
                compressed = zlib.compress(data)
        elif algo == CompressionAlgorithm.LZ4:
            try:
                import lz4.frame
                compressed = lz4.frame.compress(data)
            except ImportError:
                compressed = zlib.compress(data)
        elif algo == CompressionAlgorithm.BROTLI:
            try:
                import brotli
                compressed = brotli.compress(data)
            except ImportError:
                compressed = zlib.compress(data)
        elif algo == CompressionAlgorithm.NONE:
            compressed = data
        else:
            compressed = zlib.compress(data)

        import hashlib
        checksum = hashlib.sha256(data).hexdigest()[:16]

        block = CompressedBlock(
            data=compressed,
            algorithm=algo,
            original_size=original_size,
            compressed_size=len(compressed),
            checksum=checksum,
        )

        self._stats["total_original_bytes"] += original_size
        self._stats["total_compressed_bytes"] += len(compressed)
        self._stats["blocks_compressed"] += 1

        logger.debug(
            "Compressed %d → %d bytes (%.1f%%) [%s]",
            original_size, len(compressed),
            block.compression_ratio * 100, algo.value,
        )
        return block

    def decompress(self, block: CompressedBlock) -> bytes:
        """Decompress a compressed block."""
        if block.algorithm == CompressionAlgorithm.NONE:
            return block.data

        data: bytes
        if block.algorithm == CompressionAlgorithm.GZIP:
            data = zlib.decompress(block.data)
        elif block.algorithm == CompressionAlgorithm.ZSTD:
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                data = dctx.decompress(block.data)
            except ImportError:
                data = zlib.decompress(block.data)
        elif block.algorithm == CompressionAlgorithm.LZ4:
            try:
                import lz4.frame
                data = lz4.frame.decompress(block.data)
            except ImportError:
                data = zlib.decompress(block.data)
        elif block.algorithm == CompressionAlgorithm.BROTLI:
            try:
                import brotli
                data = brotli.decompress(block.data)
            except ImportError:
                data = zlib.decompress(block.data)
        else:
            data = zlib.decompress(block.data)

        self._stats["blocks_decompressed"] += 1
        return data

    def select_algorithm(
        self, data_type: str, storage_tier: str = "hot"
    ) -> CompressionAlgorithm:
        """
        Auto-select the best compression algorithm based on data type
        and storage tier.
        """
        if storage_tier in ("cold", "archive"):
            return CompressionAlgorithm.ZSTD  # High compression ratio
        elif data_type in ("tick", "orderbook"):
            return CompressionAlgorithm.LZ4  # Fast decompression
        elif data_type in ("kline", "quote"):
            return CompressionAlgorithm.ZSTD  # Balanced
        else:
            return self.DEFAULT_ALGORITHM

    @property
    def stats(self) -> dict[str, Any]:
        total_orig = self._stats["total_original_bytes"]
        total_comp = self._stats["total_compressed_bytes"]
        ratio = total_comp / total_orig if total_orig > 0 else 0.0
        return {
            **self._stats,
            "overall_compression_ratio": round(ratio, 4),
            "space_saved_pct": round((1 - ratio) * 100, 1),
        }
