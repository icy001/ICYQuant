"""
TOML Configuration Source.

Loads configuration from TOML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class TOMLSource(ConfigurationSource):
    """
    Loads configuration from TOML files.
    """

    name = "toml"
    priority = ConfigurationPriority.TOML

    def __init__(
        self,
        path: str,
    ) -> None:
        self._path = path

    def load(self) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        p = Path(self._path)
        if not p.exists():
            return {}

        try:
            import tomllib
        except ImportError:
            try:
                import toml as tomllib
            except ImportError:
                raise ImportError(
                    "toml is required for TOML source. "
                    "Install with: pip install toml"
                )

        with open(p, "rb") as f:
            data = tomllib.load(f)

        if not isinstance(data, dict):
            return {"value": data}

        return self._flatten(data)

    def _flatten(
        self,
        data: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Flatten nested dictionaries using dot notation."""
        result: Dict[str, Any] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value
        return result
