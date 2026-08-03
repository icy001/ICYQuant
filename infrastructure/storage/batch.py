"""
Batch transfer for storage.

Provides batch upload/download operations
with concurrency control for efficient
bulk data transfer.
"""

from __future__ import annotations

import asyncio
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Sequence,
    Tuple,
)


class BatchTransfer:
    """
    Batch transfer operations.

    Provides concurrent batch processing
    for storage operations with configurable
    concurrency and error handling.

    Features:
    - Concurrent upload/download with semaphore
    - Per-operation error isolation
    - Progress tracking
    - Result aggregation

    Usage:
        batch = BatchTransfer(max_concurrent=5)
        results = await batch.upload_many(
            service,
            [("key1", data1), ("key2", data2)],
        )
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        continue_on_error: bool = True,
    ) -> None:
        """
        Initialize batch transfer.

        Args:
            max_concurrent: Maximum concurrent operations.
            continue_on_error: Continue if one operation fails.
        """

        self._max_concurrent = max_concurrent
        self._continue_on_error = continue_on_error
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        """
        Get or create semaphore.

        Returns:
            Asyncio semaphore instance.
        """

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(
                self._max_concurrent
            )
        return self._semaphore

    async def upload_many(
        self,
        service: Any,
        files: Sequence[Tuple[str, bytes]],
        content_type: Optional[str] = None,
    ) -> List[Any]:
        """
        Upload multiple files concurrently.

        Args:
            service: StorageService instance.
            files: List of (key, data) tuples.
            content_type: Default content type.

        Returns:
            List of ObjectMetadata results.
        """

        async def _upload_one(
            key: str,
            data: bytes,
        ) -> Any:
            async with self._get_semaphore():
                return await service.upload(
                    key,
                    data,
                    content_type=content_type,
                )

        tasks = [
            _upload_one(key, data)
            for key, data in files
        ]

        return await self._gather_results(tasks)

    async def download_many(
        self,
        service: Any,
        keys: Sequence[str],
    ) -> List[Tuple[str, bytes]]:
        """
        Download multiple files concurrently.

        Args:
            service: StorageService instance.
            keys: List of object keys.

        Returns:
            List of (key, data) tuples.
        """

        async def _download_one(
            key: str,
        ) -> Tuple[str, bytes]:
            async with self._get_semaphore():
                data = await service.download(key)
                return key, data

        tasks = [_download_one(key) for key in keys]

        return await self._gather_results(tasks)

    async def delete_many(
        self,
        service: Any,
        keys: Sequence[str],
    ) -> List[str]:
        """
        Delete multiple objects concurrently.

        Args:
            service: StorageService instance.
            keys: List of object keys.

        Returns:
            List of successfully deleted keys.
        """

        async def _delete_one(
            key: str,
        ) -> str:
            async with self._get_semaphore():
                await service.delete(key)
                return key

        tasks = [_delete_one(key) for key in keys]

        return await self._gather_results(tasks)

    async def copy_many(
        self,
        service: Any,
        mappings: Sequence[Tuple[str, str]],
    ) -> List[Any]:
        """
        Copy multiple objects concurrently.

        Args:
            service: StorageService instance.
            mappings: List of (source, target) tuples.

        Returns:
            List of ObjectMetadata results.
        """

        async def _copy_one(
            source: str,
            target: str,
        ) -> Any:
            async with self._get_semaphore():
                return await service.copy(
                    source, target
                )

        tasks = [
            _copy_one(src, tgt)
            for src, tgt in mappings
        ]

        return await self._gather_results(tasks)

    async def _gather_results(
        self,
        tasks: List[asyncio.Task],
    ) -> List[Any]:
        """
        Gather results from tasks with error handling.

        Args:
            tasks: List of coroutines.

        Returns:
            List of results. Failed operations
            are excluded if continue_on_error is True.
        """

        results: List[Any] = []

        if self._continue_on_error:
            gathered = await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
            for result in gathered:
                if not isinstance(
                    result, Exception
                ):
                    results.append(result)
        else:
            results = list(
                await asyncio.gather(*tasks)
            )

        return results

    @property
    def max_concurrent(
        self,
    ) -> int:
        """Get max concurrency."""
        return self._max_concurrent