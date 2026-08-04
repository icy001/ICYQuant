"""
YAML Configuration Source.

Loads configuration from YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class YAMLSource(ConfigurationSource):
    """
    Loads configuration from YAML files.

    Supports both .yaml and .yml extensions.
    """

    name = "yaml"
    priority = ConfigurationPriority.YAML

    def __init__(
        self,
        path: str,
    ) -> None:
        self._path = path

    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        p = Path(self._path)
        if not p.exists():
            return {}

        try:
            import yaml
        except ImportError:
            # Fall back to basic parsing or raise
            raise ImportError(
                "PyYAML is required for YAML source. "
                "Install with: pip install pyyaml"
            )

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}
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
