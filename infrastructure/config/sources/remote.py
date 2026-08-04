"""
Remote Configuration Source.

Loads configuration from a remote configuration server.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class RemoteSource(ConfigurationSource):
    """
    Loads configuration from a remote server.

    Supports fetching configuration from HTTP(S) endpoints
    or other remote services. This is a placeholder for
    future integration with a dedicated configuration center.
    """

    name = "remote"
    priority = ConfigurationPriority.REMOTE

    def __init__(
        self,
        url: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._available = url is not None

    def is_available(self) -> bool:
        """Check if remote source is available."""
        return self._available

    def load(self) -> Dict[str, Any]:
        """Load configuration from remote server."""
        if not self._url:
            return {}

        try:
            import urllib.request
            import json

            req = urllib.request.Request(self._url)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if isinstance(data, dict):
                return self._flatten(data)
            return {}
        except Exception:
            return {}

    def _flatten(
        self,
        data: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Flatten nested dictionaries."""
        result: Dict[str, Any] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value
        return result
