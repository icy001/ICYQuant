"""
Storage models.

Defines data models for object storage
including metadata, object info, and
container/bucket representations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ObjectMetadata:
    """
    Stored object metadata.

    Contains all metadata associated with
    a stored object including location,
    size, type, and timestamps.

    Attributes:
        bucket: Storage bucket name.
        key: Object key (path).
        size: Object size in bytes.
        etag: Entity tag / content hash.
        content_type: MIME type of the object.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        metadata: Additional custom metadata.
    """

    bucket: str = ""

    key: str = ""

    size: int = 0

    etag: str = ""

    content_type: str = "application/octet-stream"

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None

    metadata: Dict[str, str] = field(
        default_factory=dict
    )

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
            "content_type": self.content_type,
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
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> ObjectMetadata:
        """
        Create from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            ObjectMetadata instance.
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
            content_type=data.get(
                "content_type",
                "application/octet-stream",
            ),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get(
                "metadata", {}
            ),
        )


@dataclass
class BucketInfo:
    """
    Storage bucket information.

    Attributes:
        name: Bucket name.
        region: Bucket region.
        created_at: Creation timestamp.
        object_count: Number of objects.
        total_size: Total size in bytes.
    """

    name: str = ""

    region: str = ""

    created_at: Optional[datetime] = None

    object_count: int = 0

    total_size: int = 0

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "name": self.name,
            "region": self.region,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "object_count": self.object_count,
            "total_size": self.total_size,
        }


@dataclass
class StorageObject:
    """
    Reference to a stored object.

    Lightweight reference for working with
    stored objects without downloading them.

    Attributes:
        bucket: Bucket name.
        key: Object key (path).
        metadata: Object metadata.
    """

    bucket: str = ""

    key: str = ""

    metadata: Optional[ObjectMetadata] = None

    @property
    def path(
        self,
    ) -> str:
        """
        Get full object path.

        Returns:
            Bucket/key path string.
        """

        return f"{self.bucket}/{self.key}"


@dataclass
class ListResult:
    """
    List operation result.

    Attributes:
        objects: List of object references.
        prefixes: Common prefixes found.
        is_truncated: Whether more results exist.
        next_marker: Marker for next page.
    """

    objects: List[StorageObject] = field(
        default_factory=list
    )

    prefixes: List[str] = field(
        default_factory=list
    )

    is_truncated: bool = False

    next_marker: str = ""

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "objects": [
                {
                    "bucket": obj.bucket,
                    "key": obj.key,
                    "metadata": (
                        obj.metadata.to_dict()
                        if obj.metadata
                        else None
                    ),
                }
                for obj in self.objects
            ],
            "prefixes": self.prefixes,
            "is_truncated": self.is_truncated,
            "next_marker": self.next_marker,
        }
