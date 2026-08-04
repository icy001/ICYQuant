"""Plugin manifest parsing and validation.

A plugin manifest describes a plugin's identity, entrypoint, permissions,
dependencies, capabilities, and configuration. Manifests are typically
authored as YAML files and loaded at plugin discovery time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml


def _looks_like_version(version: str) -> bool:
    """Heuristic check that a string resembles a semantic version.

    Accepts strings with at least one numeric dot-separated component,
    optionally prefixed with ``v`` (e.g. ``"1.2.3"``, ``"v2.0"``).
    """
    if not version:
        return False
    cleaned = version.strip().lstrip("vV")
    parts = cleaned.split(".")
    for part in parts:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits:
            return True
    return False


@dataclass
class PluginManifest:
    """Parsed plugin manifest.

    Attributes:
        id: Unique plugin identifier (slug).
        name: Human-readable plugin name.
        version: Semantic version string (e.g. ``"1.2.3"``).
        api: API version the plugin targets (default ``"v1"``).
        entrypoint: Dotted module path or callable reference for the plugin.
        author: Plugin author.
        description: Human-readable description.
        permissions: Permission scopes requested by the plugin.
        dependencies: Plugin ids this plugin depends on.
        capabilities: Capabilities provided by the plugin.
        config: Default configuration mapping.
        metadata: Arbitrary metadata mapping.
    """

    id: str
    name: str
    version: str
    api: str = "v1"
    entrypoint: str = ""
    author: str = ""
    description: str = ""
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> PluginManifest:
        """Build a manifest from a dictionary."""
        if data is None:
            data = {}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            api=str(data.get("api", "v1")),
            entrypoint=str(data.get("entrypoint", "")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            permissions=list(data.get("permissions", []) or []),
            dependencies=list(data.get("dependencies", []) or []),
            capabilities=list(data.get("capabilities", []) or []),
            config=dict(data.get("config", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    @classmethod
    def from_yaml(cls, path: str) -> PluginManifest:
        """Load a manifest from a YAML file path."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return cls.from_yaml_string(content)

    @classmethod
    def from_yaml_string(cls, content: str) -> PluginManifest:
        """Parse a manifest from a YAML string."""
        data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            raise ValueError("Manifest YAML must parse to a mapping")
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Serialize the manifest to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "api": self.api,
            "entrypoint": self.entrypoint,
            "author": self.author,
            "description": self.description,
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "capabilities": list(self.capabilities),
            "config": dict(self.config),
            "metadata": dict(self.metadata),
        }

    def to_yaml(self) -> str:
        """Serialize the manifest to a YAML string."""
        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    def validate(self) -> List[str]:
        """Validate the manifest and return a list of error messages.

        An empty list indicates a valid manifest.
        """
        errors: List[str] = []
        if not self.id:
            errors.append("Manifest field 'id' is required")
        elif not self.id.replace("-", "").replace("_", "").replace(".", "").isalnum():
            errors.append(
                f"Manifest field 'id' must be a slug "
                f"(alphanumeric, hyphens, underscores, dots): {self.id!r}"
            )
        if not self.name:
            errors.append("Manifest field 'name' is required")
        if not self.version:
            errors.append("Manifest field 'version' is required")
        elif not _looks_like_version(self.version):
            errors.append(
                f"Manifest field 'version' must be a semantic version "
                f"(e.g. '1.2.3'): {self.version!r}"
            )
        if not self.api:
            errors.append("Manifest field 'api' is required")
        if not isinstance(self.permissions, list):
            errors.append("Manifest field 'permissions' must be a list")
        if not isinstance(self.dependencies, list):
            errors.append("Manifest field 'dependencies' must be a list")
        if not isinstance(self.capabilities, list):
            errors.append("Manifest field 'capabilities' must be a list")
        if not isinstance(self.config, dict):
            errors.append("Manifest field 'config' must be a mapping")
        if not isinstance(self.metadata, dict):
            errors.append("Manifest field 'metadata' must be a mapping")
        return errors

    def is_compatible(self, api_version: str = "v1") -> bool:
        """Check whether the manifest targets a compatible API version.

        Compatibility is currently defined as an exact match on the API
        version string.
        """
        return self.api == api_version
