"""
DotEnv loader.

Loads environment variables from .env files
in the standard order:

    .env (base)
    .env.local (local overrides)
    .env.{environment} (environment-specific)
    .env.{environment}.local (local env overrides)

Each file overrides values from previous files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class DotEnvLoader:
    """
    Loads environment variables from .env files.

    Supports the standard .env file loading
    convention used by many frameworks.

    Loading Order (later files override earlier):
    1. .env (base configuration)
    2. .env.local (local development overrides)
    3. .env.{environment} (environment-specific)
    4. .env.{environment}.local (local env overrides)

    Usage:
        loader = DotEnvLoader()
        variables = loader.load_all(environment="development")
    """

    # .env file patterns to load in order
    ENV_FILE_PATTERNS = [
        ".env",
        ".env.local",
        ".env.{env}",
        ".env.{env}.local",
    ]

    # Regex for parsing .env lines
    LINE_PATTERN = re.compile(
        r'^\s*(?:export\s+)?'
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*'
        r'(.*?)\s*$'
    )

    def __init__(
        self,
        base_dir: Optional[str] = None,
    ) -> None:
        """
        Initialize DotEnv loader.

        Args:
            base_dir: Base directory to search for .env files.
                      Defaults to current working directory.
        """
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()

    def load(
        self,
        path: str = ".env",
    ) -> Dict[str, Any]:
        """
        Load a single .env file.

        Args:
            path: Path to .env file.

        Returns:
            Dictionary of parsed variables.
        """
        filepath = self._base_dir / path
        if not filepath.exists():
            return {}

        variables: Dict[str, Any] = {}

        try:
            content = filepath.read_text(encoding="utf-8")
            for line in content.splitlines():
                parsed = self._parse_line(line)
                if parsed:
                    key, value = parsed
                    variables[key] = value
        except (OSError, UnicodeDecodeError):
            pass

        return variables

    def load_all(
        self,
        environment: str = "development",
    ) -> Dict[str, Any]:
        """
        Load all .env files in standard order.

        Later files override earlier ones.

        Args:
            environment: Active environment name.

        Returns:
            Merged dictionary of all variables.
        """
        result: Dict[str, Any] = {}

        for pattern in self.ENV_FILE_PATTERNS:
            filename = pattern.replace("{env}", environment)
            filepath = self._base_dir / filename

            if filepath.exists():
                variables = self.load(filename)
                result.update(variables)

        return result

    def load_and_set_env(
        self,
        environment: str = "development",
        override: bool = False,
    ) -> None:
        """
        Load .env files and set them as os.environ variables.

        Args:
            environment: Active environment.
            override: Whether to override existing env vars.
        """
        variables = self.load_all(environment)

        for key, value in variables.items():
            key_upper = key.upper()
            if override or key_upper not in os.environ:
                os.environ[key_upper] = str(value)

    def _parse_line(
        self,
        line: str,
    ) -> Optional[tuple]:
        """
        Parse a single .env line.

        Args:
            line: Line content.

        Returns:
            (key, value) tuple or None.
        """
        # Skip comments and empty lines
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return None

        match = self.LINE_PATTERN.match(stripped)
        if not match:
            return None

        key = match.group(1)
        value = self._clean_value(match.group(2))

        return (key, value)

    def _clean_value(
        self,
        value: str,
    ) -> Any:
        """
        Clean and parse a .env value.

        Handles:
        - Quoted strings (single and double)
        - Comments after values
        - Type conversion (int, float, bool)
        """
        # Remove trailing comments
        if " #" in value:
            # Only split if # is not inside quotes
            if not (value.startswith('"') or value.startswith("'")):
                value = value.split(" #")[0]

        # Remove whitespace
        value = value.strip()

        # Handle quoted strings
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Handle empty string
        if not value:
            return ""

        # Try type conversion
        return self._convert_type(value)

    def _convert_type(
        self,
        value: str,
    ) -> Any:
        """Convert string value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
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

    def find_env_files(
        self,
        environment: str = "development",
    ) -> List[str]:
        """
        Find all .env files that would be loaded.

        Args:
            environment: Active environment.

        Returns:
            List of file paths that exist.
        """
        found: List[str] = []

        for pattern in self.ENV_FILE_PATTERNS:
            filename = pattern.replace("{env}", environment)
            filepath = self._base_dir / filename
            if filepath.exists():
                found.append(filename)

        return found
