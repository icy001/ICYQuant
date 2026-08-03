"""
Storage serializer.

Provides path normalization and serialization
utilities for object storage keys, ensuring
cross-platform compatibility and consistent
key naming conventions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union


class PathSerializer:
    """
    Path serializer for object keys.

    Normalizes storage paths across platforms
    and generates consistent key names following
    the ICYQuant naming convention:
    <domain>/<category>/<yyyy>/<MM>/<dd>/<file>
    """

    @staticmethod
    def normalize(
        path: str,
    ) -> str:
        """
        Normalize a storage path.

        Converts to forward slashes, strips
        leading/trailing slashes for consistency.

        Args:
            path: Raw storage path.

        Returns:
            Normalized path string.
        """

        return (
            Path(path)
            .as_posix()
            .strip("/")
        )

    @staticmethod
    def join(
        *parts: str,
    ) -> str:
        """
        Join path components.

        Args:
            *parts: Path segments to join.

        Returns:
            Joined and normalized path.
        """

        return "/".join(
            PathSerializer.normalize(p)
            for p in parts
            if p
        )

    @staticmethod
    def generate_key(
        domain: str,
        category: str,
        filename: str,
        date: Union[datetime, None] = None,
    ) -> str:
        """
        Generate a standardized object key.

        Follows the ICYQuant naming convention:
        <domain>/<category>/<yyyy>/<MM>/<dd>/<file>

        Args:
            domain: Domain name (market, strategy, research, etc.).
            category: Category (ticks, models, reports, etc.).
            filename: Object filename.
            date: Date for the path (default: today).

        Returns:
            Full normalized object key.
        """

        if date is None:
            date = datetime.utcnow()

        return PathSerializer.join(
            domain,
            category,
            f"{date.year:04d}",
            f"{date.month:02d}",
            f"{date.day:02d}",
            filename,
        )

    @staticmethod
    def parse_key(
        key: str,
    ) -> Dict[str, str]:
        """
        Parse a standardized object key.

        Extracts components from a key following
        the ICYQuant naming convention.

        Args:
            key: Full object key.

        Returns:
            Dictionary with domain, category, year,
            month, day, file keys.
        """

        normalized = PathSerializer.normalize(key)
        parts = normalized.split("/")

        result: Dict[str, str] = {
            "domain": "",
            "category": "",
            "year": "",
            "month": "",
            "day": "",
            "file": "",
        }

        if len(parts) >= 1:
            result["domain"] = parts[0]
        if len(parts) >= 2:
            result["category"] = parts[1]
        if len(parts) >= 3:
            result["year"] = parts[2]
        if len(parts) >= 4:
            result["month"] = parts[3]
        if len(parts) >= 5:
            result["day"] = parts[4]
        if len(parts) >= 6:
            result["file"] = "/".join(parts[5:])

        return result


class ObjectSerializer:
    """
    Object content serializer.

    Handles serialization/deserialization
    of object content for storage operations.
    """

    @staticmethod
    def to_json(
        data: Any,
    ) -> bytes:
        """
        Serialize data to JSON bytes.

        Args:
            data: Any JSON-serializable data.

        Returns:
            JSON-encoded bytes.
        """

        return json.dumps(
            data,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

    @staticmethod
    def from_json(
        data: bytes,
    ) -> Any:
        """
        Deserialize JSON bytes to object.

        Args:
            data: JSON-encoded bytes.

        Returns:
            Deserialized Python object.
        """

        return json.loads(
            data.decode("utf-8")
        )

    @staticmethod
    def to_bytes(
        data: Union[str, bytes],
    ) -> bytes:
        """
        Convert string or bytes to bytes.

        Args:
            data: Input data.

        Returns:
            Bytes representation.
        """

        if isinstance(data, bytes):
            return data
        return data.encode("utf-8")
