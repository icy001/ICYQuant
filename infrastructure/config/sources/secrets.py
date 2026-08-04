"""
Secrets Configuration Source.

Loads configuration from a secrets manager.
Supports placeholder resolution.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


# Pattern for secret placeholders: ${secret:path/to/key}
SECRET_PATTERN = re.compile(
    r"\$\{secret:([^}]+)\}"
)


class SecretsSource(ConfigurationSource):
    """
    Loads configuration from a secrets manager.

    This source detects secrets placeholders
    in configuration values and resolves them.

    Placeholder format:
        ${secret:path/to/key}

    Example:
        database.password = "${secret:db/password}"
        redis.password = "${secret:redis/password}"
        api.key = "${secret:broker/api_key}"

    Note:
        This is a placeholder implementation.
        Actual secret resolution will be integrated
        with the Secrets Platform (Commit 5).
    """

    name = "secrets"
    priority = ConfigurationPriority.SECRETS

    def __init__(
        self,
        secrets: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize secrets source.

        Args:
            secrets: Pre-loaded secrets dictionary.
        """
        self._secrets = secrets or {}

    def set_secret(
        self,
        path: str,
        value: Any,
    ) -> None:
        """Store a secret value."""
        self._secrets[path] = value

    def is_available(self) -> bool:
        """Check if secrets source is available."""
        return len(self._secrets) > 0

    def load(self) -> Dict[str, Any]:
        """Load secrets (returns empty - resolution happens in resolve_secrets)."""
        return {}

    def resolve_secrets(
        self,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve secret placeholders in configuration values.

        Args:
            config: Configuration dictionary with possible placeholders.

        Returns:
            Configuration with resolved secrets.
        """
        result: Dict[str, Any] = {}
        for key, value in config.items():
            result[key] = self._resolve_value(value)
        return result

    def _resolve_value(
        self,
        value: Any,
    ) -> Any:
        """Recursively resolve secret placeholders."""
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return {k: self._resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        return value

    def _resolve_string(
        self,
        value: str,
    ) -> str:
        """Resolve secret placeholders in a string."""
        def replace_match(match: re.Match) -> str:
            secret_path = match.group(1)
            return str(self._secrets.get(secret_path, match.group(0)))

        return SECRET_PATTERN.sub(replace_match, value)
