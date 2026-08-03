"""Compression support for span export."""

from __future__ import annotations

import gzip
import io
from typing import Any, Optional


class CompressionManager:
    """
    Span data compression manager.

    Supports gzip, zstd, and snappy
    compression algorithms for reducing
    export payload size.

    Usage:
        mgr = CompressionManager(algorithm="gzip")
        compressed = mgr.compress(data)
        decompressed = mgr.decompress(compressed)
    """

    SUPPORTED = ["gzip", "zstd", "snappy", "none"]

    def __init__(self, algorithm: str = "gzip") -> None:
        self._algorithm = algorithm
        self._compress_count: int = 0
        self._decompress_count: int = 0
        self._total_compressed: int = 0
        self._total_decompressed: int = 0

    @property
    def algorithm(self) -> str:
        return self._algorithm

    def compress(self, data: bytes) -> bytes:
        """Compress data."""
        if self._algorithm == "none" or not data:
            return data

        if self._algorithm == "gzip":
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as f:
                f.write(data)
            result = buf.getvalue()
        elif self._algorithm == "zstd":
            try:
                import zstandard
                result = zstandard.compress(data)
            except ImportError:
                result = data
        elif self._algorithm == "snappy":
            try:
                import snappy
                result = snappy.compress(data)
            except ImportError:
                result = data
        else:
            result = data

        self._compress_count += 1
        self._total_compressed += len(result)
        return result

    def decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        if self._algorithm == "none" or not data:
            return data

        if self._algorithm == "gzip":
            buf = io.BytesIO(data)
            with gzip.GzipFile(fileobj=buf, mode="rb") as f:
                result = f.read()
        elif self._algorithm == "zstd":
            try:
                import zstandard
                result = zstandard.decompress(data)
            except ImportError:
                result = data
        elif self._algorithm == "snappy":
            try:
                import snappy
                result = snappy.decompress(data)
            except ImportError:
                result = data
        else:
            result = data

        self._decompress_count += 1
        self._total_decompressed += len(result)
        return result

    def get_stats(self) -> dict:
        return {
            "algorithm": self._algorithm,
            "compress_count": self._compress_count,
            "decompress_count": self._decompress_count,
            "total_compressed": self._total_compressed,
            "total_decompressed": self._total_decompressed,
        }
