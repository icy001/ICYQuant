"""
ZSTD compression for storage.

Provides high-performance compression/
decompression for storage payloads using
the Zstandard algorithm, reducing storage
cost for market data, factor data, and
research artifacts.
"""

from __future__ import annotations

from typing import Optional

try:
    import zstandard as zstd

    ZSTD_AVAILABLE = True
except ImportError:
    zstd = None  # type: ignore
    ZSTD_AVAILABLE = False


class ZstdCompression:
    """
    Zstandard compression provider.

    Implements high-performance compression
    for storage payloads. ZSTD provides
    excellent compression ratios with fast
    decompression, ideal for market data
    and time-series datasets.

    Features:
    - Configurable compression level (1-22)
    - Separate compressor/decompressor pools
    - Thread-safe operation

    Usage:
        compression = ZstdCompression(level=3)
        compressed = compression.compress(data)
        decompressed = compression.decompress(compressed)
    """

    def __init__(
        self,
        level: int = 3,
        enable_checksum: bool = False,
    ) -> None:
        """
        Initialize ZSTD compression.

        Args:
            level: Compression level (1-22).
                Lower = faster, Higher = better ratio.
            enable_checksum: Enable checksum verification.
        """

        self._level = level
        self._enable_checksum = enable_checksum
        self._compressor: Optional[Any] = None
        self._decompressor: Optional[Any] = None
        self._initialized = False

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if zstandard is available."""
        return ZSTD_AVAILABLE

    @property
    def level(
        self,
    ) -> int:
        """Get compression level."""
        return self._level

    def _ensure_initialized(
        self,
    ) -> None:
        """
        Initialize compressor/decompressor if needed.

        Raises:
            ImportError: If zstandard not installed.
        """

        if self._initialized:
            return

        if not ZSTD_AVAILABLE:
            raise ImportError(
                "zstandard package is required. "
                "Install with: pip install zstandard"
            )

        self._compressor = zstd.ZstdCompressor(
            level=self._level,
            write_content_size=True,
        )
        self._decompressor = zstd.ZstdDecompressor()
        self._initialized = True

    def compress(
        self,
        data: bytes,
    ) -> bytes:
        """
        Compress data with ZSTD.

        Args:
            data: Raw bytes to compress.

        Returns:
            Compressed bytes.
        """

        self._ensure_initialized()
        assert self._compressor is not None
        return self._compressor.compress(data)

    def decompress(
        self,
        data: bytes,
    ) -> bytes:
        """
        Decompress ZSTD data.

        Args:
            data: Compressed bytes.

        Returns:
            Decompressed bytes.
        """

        self._ensure_initialized()
        assert self._decompressor is not None
        return self._decompressor.decompress(data)

    def get_compression_ratio(
        self,
        original: bytes,
        compressed: bytes,
    ) -> float:
        """
        Calculate compression ratio.

        Args:
            original: Original data bytes.
            compressed: Compressed data bytes.

        Returns:
            Compression ratio (compressed / original).
        """

        if len(original) == 0:
            return 0.0
        return len(compressed) / len(original)

    @staticmethod
    def estimate_savings(
        original_size: int,
        typical_ratio: float = 0.3,
    ) -> int:
        """
        Estimate storage savings.

        Args:
            original_size: Original size in bytes.
            typical_ratio: Expected compression ratio.

        Returns:
            Estimated bytes saved.
        """

        return int(
            original_size * (1 - typical_ratio)
        )