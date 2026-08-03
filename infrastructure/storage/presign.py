"""
Presigned URL support.

Provides data structures for time-limited
direct access URLs for objects, enabling
secure temporary access without exposing
credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional


@dataclass
class PresignedUrl:
    """
    Presigned URL for object access.

    Contains a time-limited URL that provides
    direct access to an object without requiring
    credentials. Useful for browser downloads,
    frontend uploads, and third-party integrations.

    Attributes:
        url: The presigned URL.
        expires_in: Time until URL expires.
        method: HTTP method (GET or PUT).
        key: Object key this URL is for.
    """

    url: str = ""

    expires_in: timedelta = timedelta(
        seconds=0
    )

    method: str = "GET"

    key: str = ""

    @property
    def expires_seconds(
        self,
    ) -> int:
        """
        Get expiration in seconds.

        Returns:
            Number of seconds until expiration.
        """

        return int(
            self.expires_in.total_seconds()
        )

    def is_expired(
        self,
        elapsed: timedelta,
    ) -> bool:
        """
        Check if URL has expired.

        Args:
            elapsed: Time elapsed since URL creation.

        Returns:
            True if URL has expired.
        """

        return elapsed >= self.expires_in

    def to_dict(
        self,
    ) -> dict:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "url": self.url,
            "expires_in": self.expires_seconds,
            "method": self.method,
            "key": self.key,
        }