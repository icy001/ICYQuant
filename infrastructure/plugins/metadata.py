"""Plugin metadata management.

Provides plugin metadata records and an in-memory registry for storing
and querying metadata across the ICYQuant plugin framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a value into a datetime, returning None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


@dataclass
class PluginMetadata:
    """Metadata describing a registered plugin.

    Attributes:
        plugin_id: Unique plugin identifier.
        name: Human-readable plugin name.
        version: Plugin version string.
        author: Plugin author.
        description: Human-readable description.
        homepage: Optional homepage URL.
        license: Optional license identifier.
        tags: Free-form tags for categorization.
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC).
        extra: Arbitrary additional metadata.
    """

    plugin_id: str
    name: str
    version: str
    author: str
    description: str = ""
    homepage: str = ""
    license: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the metadata to a dictionary.

        Datetime fields are serialized as ISO 8601 strings.
        """
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "homepage": self.homepage,
            "license": self.license,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PluginMetadata:
        """Deserialize metadata from a dictionary."""
        if data is None:
            data = {}
        meta = cls(
            plugin_id=str(data.get("plugin_id", "")),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            homepage=str(data.get("homepage", "")),
            license=str(data.get("license", "")),
            tags=list(data.get("tags", []) or []),
            extra=dict(data.get("extra", {}) or {}),
        )
        created = _parse_datetime(data.get("created_at"))
        updated = _parse_datetime(data.get("updated_at"))
        if created is not None:
            meta.created_at = created
        if updated is not None:
            meta.updated_at = updated
        return meta

    def merge(self, other: Dict[str, Any]) -> None:
        """Merge additional data into the metadata.

        Known top-level fields are updated when present in ``other``;
        any unknown keys are merged into the ``extra`` dictionary. Tag
        lists are unioned. The ``updated_at`` timestamp is refreshed.
        """
        known_keys = {
            "plugin_id", "name", "version", "author", "description",
            "homepage", "license", "tags", "created_at", "updated_at", "extra",
        }
        if "name" in other:
            self.name = str(other["name"])
        if "version" in other:
            self.version = str(other["version"])
        if "author" in other:
            self.author = str(other["author"])
        if "description" in other:
            self.description = str(other["description"])
        if "homepage" in other:
            self.homepage = str(other["homepage"])
        if "license" in other:
            self.license = str(other["license"])
        if "tags" in other and isinstance(other["tags"], list):
            for tag in other["tags"]:
                self.add_tag(str(tag))
        if "extra" in other and isinstance(other["extra"], dict):
            self.extra.update(other["extra"])
        for key, value in other.items():
            if key not in known_keys:
                self.extra[key] = value
        self.updated_at = datetime.utcnow()

    def has_tag(self, tag: str) -> bool:
        """Return True if the metadata has the given tag."""
        return tag in self.tags

    def add_tag(self, tag: str) -> None:
        """Add a tag if it is non-empty and not already present."""
        tag = str(tag)
        if tag and tag not in self.tags:
            self.tags.append(tag)


class MetadataRegistry:
    """Registry for plugin metadata.

    Stores :class:`PluginMetadata` records keyed by plugin id and
    supports lookup, listing, and search by tag and/or author.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, PluginMetadata] = {}

    def register(self, metadata: PluginMetadata) -> None:
        """Register or replace metadata for a plugin id."""
        self._entries[metadata.plugin_id] = metadata

    def unregister(self, plugin_id: str) -> None:
        """Remove metadata for a plugin id, if present."""
        self._entries.pop(plugin_id, None)

    def get(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Retrieve metadata for a plugin id."""
        return self._entries.get(plugin_id)

    def list_all(self) -> List[PluginMetadata]:
        """Return all registered metadata entries."""
        return list(self._entries.values())

    def search(self, tag: str = "", author: str = "") -> List[PluginMetadata]:
        """Search metadata by tag and/or author.

        When both ``tag`` and ``author`` are provided, entries must
        match both criteria. Empty filters match all entries.
        """
        results: List[PluginMetadata] = []
        for meta in self._entries.values():
            if tag and not meta.has_tag(tag):
                continue
            if author and meta.author != author:
                continue
            results.append(meta)
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the registry to a dictionary keyed by plugin id."""
        return {
            "count": len(self._entries),
            "entries": {
                plugin_id: meta.to_dict()
                for plugin_id, meta in self._entries.items()
            },
        }
