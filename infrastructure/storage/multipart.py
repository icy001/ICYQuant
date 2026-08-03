"""
Multipart upload support.

Provides data structures and utilities for
managing large file uploads via multipart
protocol, supporting chunked uploads and
resume capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PartInfo:
    """
    Multipart upload part information.

    Attributes:
        part_number: Part sequence number (1-based).
        size: Part size in bytes.
        etag: Part entity tag / hash.
    """

    part_number: int = 0

    size: int = 0

    etag: str = ""


@dataclass
class MultipartUpload:
    """
    Multipart upload session.

    Tracks the state of an ongoing multipart
    upload operation, including upload ID,
    completed parts, and completion status.

    Attributes:
        upload_id: Unique upload session ID.
        object_key: Target object key.
        parts_uploaded: Number of uploaded parts.
        total_parts: Expected total parts.
        parts: List of uploaded part information.
        completed: Whether upload is complete.
        aborted: Whether upload was aborted.
    """

    upload_id: str = ""

    object_key: str = ""

    parts_uploaded: int = 0

    total_parts: int = 0

    parts: List[PartInfo] = field(
        default_factory=list
    )

    completed: bool = False

    aborted: bool = False

    @property
    def progress(
        self,
    ) -> float:
        """
        Get upload progress ratio.

        Returns:
            Progress as float between 0.0 and 1.0.
        """

        if self.total_parts == 0:
            return 0.0
        return self.parts_uploaded / self.total_parts

    @property
    def is_active(
        self,
    ) -> bool:
        """
        Check if upload is still active.

        Returns:
            True if not completed or aborted.
        """

        return not (
            self.completed or self.aborted
        )

    def add_part(
        self,
        part_number: int,
        size: int,
        etag: str,
    ) -> None:
        """
        Record an uploaded part.

        Args:
            part_number: Part sequence number.
            size: Part size in bytes.
            etag: Part entity tag.
        """

        self.parts.append(
            PartInfo(
                part_number=part_number,
                size=size,
                etag=etag,
            )
        )
        self.parts_uploaded = len(self.parts)

    def to_dict(
        self,
    ) -> Dict[str, object]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "upload_id": self.upload_id,
            "object_key": self.object_key,
            "parts_uploaded": self.parts_uploaded,
            "total_parts": self.total_parts,
            "progress": self.progress,
            "completed": self.completed,
            "aborted": self.aborted,
        }