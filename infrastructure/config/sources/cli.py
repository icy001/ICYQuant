"""
CLI Arguments Configuration Source.

Loads configuration from command-line arguments.
"""

from __future__ import annotations

import sys
import shlex
from typing import Any, Dict, List, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class CLISource(ConfigurationSource):
    """
    Loads configuration from command-line arguments.

    Parses command-line arguments in the format:
        --key=value or --key value

    Supports dot notation for nested keys:
        --server.port=8080 -> server.port=8080
    """

    name = "cli"
    priority = ConfigurationPriority.CLI

    def __init__(
        self,
        args: Optional[List[str]] = None,
    ) -> None:
        self._args = args or sys.argv[1:]

    def load(self) -> Dict[str, Any]:
        """Load configuration from command-line arguments."""
        result: Dict[str, Any] = {}

        i = 0
        while i < len(self._args):
            arg = self._args[i]

            if arg.startswith("--"):
                # Remove -- prefix
                key = arg[2:]

                if "=" in key:
                    # --key=value format
                    key, value = key.split("=", 1)
                    result[key] = self._parse_value(value)
                elif i + 1 < len(self._args):
                    # --key value format
                    i += 1
                    result[key] = self._parse_value(self._args[i])
                else:
                    # Boolean flag (no value)
                    result[key] = True

            elif arg.startswith("-"):
                # Short form: -k value
                key = arg[1:]
                if i + 1 < len(self._args):
                    i += 1
                    result[key] = self._parse_value(self._args[i])
                else:
                    result[key] = True

            i += 1

        return result

    def _parse_value(
        self,
        value: str,
    ) -> Any:
        """Parse a string value to appropriate type."""
        # Try JSON for complex types
        try:
            import json
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

        # Boolean
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False

        # Integer
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

        # Float
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        return value
