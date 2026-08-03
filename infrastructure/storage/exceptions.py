"""
Storage exceptions.

Defines exception hierarchy for object
storage operations, covering upload, download,
delete, and bucket operations.
"""

from __future__ import annotations

from typing import Optional


class StorageError(Exception):
    """
    Base storage exception.

    All storage-related exceptions inherit
    from this class for unified error handling.
    """

    def __init__(
        self,
        message: str = "",
        bucket: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:

        self.bucket = bucket
        self.key = key

        super().__init__(message)


class StorageConnectionError(
    StorageError,
):
    """
    Storage connection error.

    Raised when unable to connect to the
    storage provider endpoint.
    """

    pass


class StorageTimeoutError(
    StorageError,
):
    """
    Storage operation timeout.

    Raised when a storage operation exceeds
    the configured timeout.
    """

    pass


class UploadError(
    StorageError,
):
    """
    Upload failed.

    Raised when an object upload operation
    fails due to network, permission, or
    size constraints.
    """

    pass


class DownloadError(
    StorageError,
):
    """
    Download failed.

    Raised when an object download operation
    fails or the requested object does not exist.
    """

    pass


class DeleteError(
    StorageError,
):
    """
    Delete failed.

    Raised when an object or bucket deletion
    fails due to permission or constraint issues.
    """

    pass


class BucketError(
    StorageError,
):
    """
    Bucket operation failed.

    Raised when a bucket-level operation
    (create, delete, list) fails.
    """

    pass


class ObjectNotFoundError(
    DownloadError,
):
    """
    Object not found.

    Raised when a requested object key
    does not exist in the bucket.
    """

    def __init__(
        self,
        key: str,
        bucket: Optional[str] = None,
    ) -> None:

        message = f"Object not found: {key}"
        if bucket:
            message = f"{message} in bucket: {bucket}"

        super().__init__(
            message,
            bucket=bucket,
            key=key,
        )


class BucketNotFoundError(
    BucketError,
):
    """
    Bucket not found.

    Raised when a requested bucket does not exist.
    """

    def __init__(
        self,
        bucket: str,
    ) -> None:

        super().__init__(
            f"Bucket not found: {bucket}",
            bucket=bucket,
        )
