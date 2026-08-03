"""
Extended object metadata.

Provides comprehensive metadata model for
stored objects including versioning, storage
class, cache control, and custom attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ExtendedMetadata:
    """
    Extended object metadata.

    Comprehensive metadata model supporting
    all common object attributes across
    different storage providers.

    Attributes:
        bucket: Storage bucket name.
        key: Object key (path).
        size: Object size in bytes.
        etag: Entity tag / content hash.
        version_id: Object version identifier.
        storage_class: Storage class (STANDARD, GLACIER, etc.).
        content_type: MIME type of the object.
        content_encoding: Content encoding (gzip, etc.).
        cache_control: Cache control directive.
        content_disposition: Content disposition.
        metadata: Custom user metadata.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    bucket: str = ""

    key: str = ""

    size: int = 0

    etag: str = ""

    version_id: Optional[str] = None

    storage_class: Optional[str] = None

    content_type: str = "application/octet-stream"

    content_encoding: Optional[str] = None

    cache_control: Optional[str] = None

    content_disposition: Optional[str] = None

    metadata: Dict[str, str] = field(
        default_factory=dict
    )

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "bucket": self.bucket,
            "key": self.key,
            "size": self.size,
            "etag": self.etag,
            "version_id": self.version_id,
            "storage_class": self.storage_class,
            "content_type": self.content_type,
            "content_encoding": self.content_encoding,
            "cache_control": self.cache_control,
            "content_disposition": (
                self.content_disposition
            ),
            "metadata": self.metadata,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> ExtendedMetadata:
        """
        Create from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            ExtendedMetadata instance.
        """

        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(
                created_at
            )
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(
                updated_at
            )

        return cls(
            bucket=data.get("bucket", ""),
            key=data.get("key", ""),
            size=data.get("size", 0),
            etag=data.get("etag", ""),
            version_id=data.get("version_id"),
            storage_class=data.get(
                "storage_class"
            ),
            content_type=data.get(
                "content_type",
                "application/octet-stream",
            ),
            content_encoding=data.get(
                "content_encoding"
            ),
            cache_control=data.get(
                "cache_control"
            ),
            content_disposition=data.get(
                "content_disposition"
            ),
            metadata=data.get(
                "metadata", {}
            ),
            created_at=created_at,
            updated_at=updated_at,
        )