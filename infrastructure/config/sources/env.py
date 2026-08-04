"""
Environment Variable Configuration Source.

Loads configuration from environment variables.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class EnvironmentSource(ConfigurationSource):
    """
    Loads configuration from environment variables.

    Uses a prefix to identify which environment variables
    belong to the application. Environment variables are
    automatically parsed for types (int, float, bool, list).

    Rules:
    - Variable names are lowercased and dots replace underscores
    - Supported formats:
        * ICYQUANT_PORT=8080 -> port=8080 (int)
        * ICYQUANT_DEBUG=true -> debug=True (bool)
        * ICYQUANT_HOST=localhost -> host=localhost (str)
        * ICYQUANT_TAGS=python,go -> tags=["python", "go"] (list)
    """

    name = "env"
    priority = ConfigurationPriority.ENV

    def __init__(
        self,
        prefix: str = "ICYQUANT_",
    ) -> None:
        self._prefix = prefix

    def load(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        result: Dict[str, Any] = {}
        prefix_lower = self._prefix.lower()

        for key, value in os.environ.items():
            if not key.lower().startswith(prefix_lower):
                continue

            # Remove prefix and convert to dot notation
            config_key = key[len(self._prefix):].lower().replace("_", ".")
            parsed_value = self._parse_value(value)
            result[config_key] = parsed_value

        return result

    def _parse_value(
        self,
        value: str,
    ) -> Any:
        """Parse a string value to the appropriate type."""
        # Try JSON first for complex types
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False

        # Try integer
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

        # Try float
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        # Try list (comma-separated)
        if "," in value:
            parts = [p.strip() for p in value.split(",")]
            return [self._parse_single(p) for p in parts]

        return value

    def _parse_single(
        self,
        value: str,
    ) -> Any:
        """Parse a single string value."""
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value
