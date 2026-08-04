"""
Environment profile loader.

Loads environment profiles from various
sources including files, dictionaries,
and the standard profile set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import EnvironmentProfile


class ProfileLoader:
    """
    Loads environment profiles.

    Supports loading from:
    - Python dictionaries
    - YAML files
    - JSON files
    - The standard profile set

    Usage:
        loader = ProfileLoader()
        profile = loader.load_from_dict({
            "name": "custom",
            "parent": "development",
            "variables": {"key": "value"}
        })
    """

    def load_from_dict(
        self,
        data: Dict[str, Any],
    ) -> EnvironmentProfile:
        """
        Load a profile from a dictionary.

        Args:
            data: Profile data dictionary.

        Returns:
            EnvironmentProfile instance.
        """
        return EnvironmentProfile(
            name=data.get("name", "custom"),
            parent=data.get("parent"),
            description=data.get("description", ""),
            variables=data.get("variables", {}),
            readonly=data.get("readonly", False),
        )

    def load_from_file(
        self,
        path: str,
    ) -> List[EnvironmentProfile]:
        """
        Load profiles from a file.

        Supports YAML and JSON formats.

        Args:
            path: File path.

        Returns:
            List of EnvironmentProfile instances.
        """
        p = Path(path)
        if not p.exists():
            return []

        ext = p.suffix.lower()

        try:
            if ext in (".yaml", ".yml"):
                return self._load_yaml(p)
            elif ext == ".json":
                return self._load_json(p)
            else:
                return []
        except Exception:
            return []

    def load_standard(
        self,
        name: str,
    ) -> Optional[EnvironmentProfile]:
        """
        Load a standard profile by name.

        Args:
            name: Profile name.

        Returns:
            EnvironmentProfile or None.
        """
        from .profile import STANDARD_PROFILES
        return STANDARD_PROFILES.get(name)

    def load_all_standard(
        self,
    ) -> List[EnvironmentProfile]:
        """Load all standard profiles."""
        from .profile import STANDARD_PROFILES
        return list(STANDARD_PROFILES.values())

    def _load_yaml(
        self,
        path: Path,
    ) -> List[EnvironmentProfile]:
        """Load profiles from YAML file."""
        try:
            import yaml
        except ImportError:
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if isinstance(data, dict) and "profiles" in data:
            profiles_data = data["profiles"]
        elif isinstance(data, list):
            profiles_data = data
        else:
            profiles_data = [data]

        return [self.load_from_dict(p) for p in profiles_data]

    def _load_json(
        self,
        path: Path,
    ) -> List[EnvironmentProfile]:
        """Load profiles from JSON file."""
        import json

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "profiles" in data:
            profiles_data = data["profiles"]
        elif isinstance(data, list):
            profiles_data = data
        else:
            profiles_data = [data]

        return [self.load_from_dict(p) for p in profiles_data]
