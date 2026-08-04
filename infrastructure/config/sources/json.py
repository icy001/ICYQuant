"""
JSON Configuration Source.

Loads configuration from JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .base import ConfigurationSource
from ..priority import ConfigurationPriority


class JSONSource(ConfigurationSource):
    """
    Loads configuration from JSON files.
    """

    name = "json"
    priority = ConfigurationPriority.JSON

    def __init__(
        self,
        path: str,
    ) -> None:
        self._path = path

    def load(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        p = Path(self._path)
        if not p.exists():
            return {}

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

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
