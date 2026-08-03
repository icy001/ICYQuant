"""
Streaming API for storage.

Provides async streaming interfaces for
efficient handling of large objects without
loading entire content into memory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Dict, Optional


class StorageStream:
    """
    Storage streaming interface.

    Provides async streaming methods for
    uploading and downloading large objects
    chunk by chunk.
    """

    def __init__(
        self,
        client,
    ) -> None:
        """
        Initialize storage stream.

        Args:
            client: Storage client for stream operations.
        """

        self._client = client

    async def upload_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        chunk_size: int = 1024 * 1024,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Upload data from an async stream.

        Collects chunks from the stream and uploads
        them as a single object. For large uploads,
        use multipart upload instead.

        Args:
            key: Object key (path).
            stream: Async iterator yielding data chunks.
            chunk_size: Buffer size for collecting chunks.
            content_type: MIME type for the object.
            metadata: Optional custom metadata.

        Note:
            This buffers all data in memory before upload.
            For large files, use multipart upload.
        """

        chunks = []
        total_size = 0

        async for chunk in stream:
            chunks.append(chunk)
            total_size += len(chunk)

        data = b"".join(chunks)

        await self._client.upload(
            key=key,
            data=data,
            content_type=content_type
            or "application/octet-stream",
            metadata=metadata,
        )

    async def download_stream(
        self,
        key: str,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        """
        Download data as an async stream.

        Yields chunks of data from the object
        to enable memory-efficient processing.

        Args:
            key: Object key (path).
            chunk_size: Size of each chunk in bytes.

        Yields:
            Bytes chunks from the object.

        Note:
            For providers without native streaming,
            downloads entire object and yields chunks.
        """

        data = await self._client.download(key)

        for i in range(
            0, len(data), chunk_size
        ):
            yield data[i : i + chunk_size]

    async def download_range(
        self,
        key: str,
        offset: int,
        length: int,
    ) -> bytes:
        """
        Download a byte range from an object.

        Useful for reading specific portions of
        large objects without downloading the
        entire file.

        Args:
            key: Object key (path).
            offset: Starting byte offset.
            length: Number of bytes to read.

        Returns:
            Requested byte range.

        Note:
            This is a convenience method that downloads
            the entire object and extracts the range.
            Provider-specific implementations may optimize.
        """

        data = await self._client.download(key)

        return data[offset : offset + length]