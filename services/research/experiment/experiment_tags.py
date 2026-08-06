"""Experiment Tags — tag management for experiment categorization and discovery.

Provides structured tag operations including:
* Add/remove tags
* Tag search and filtering
* Tag namespace support
* Tag statistics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ExperimentTags:
    """Manages tags for experiment categorization.

    Supports:
    * Flat tags: ["momentum", "daily", "v1"]
    * Namespaced tags: {"env": "prod", "model": "xgboost"}
    * Bulk operations and statistics
    """

    tags: List[str] = field(default_factory=list)
    namespaced_tags: Dict[str, str] = field(default_factory=dict)

    # ── flat tags ─────────────────────────────────────────────────────────

    def add_tag(self, tag: str) -> None:
        """Add a flat tag (no-op if already present)."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a flat tag."""
        if tag in self.tags:
            self.tags.remove(tag)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def has_any_tag(self, tags: List[str]) -> bool:
        return any(t in self.tags for t in tags)

    def has_all_tags(self, tags: List[str]) -> bool:
        return all(t in self.tags for t in tags)

    # ── namespaced tags ───────────────────────────────────────────────────

    def set_namespaced(self, namespace: str, value: str) -> None:
        """Set a namespaced tag value."""
        self.namespaced_tags[namespace] = value

    def get_namespaced(self, namespace: str) -> Optional[str]:
        return self.namespaced_tags.get(namespace)

    def remove_namespaced(self, namespace: str) -> None:
        self.namespaced_tags.pop(namespace, None)

    # ── bulk operations ───────────────────────────────────────────────────

    def add_tags(self, tags: List[str]) -> None:
        for tag in tags:
            self.add_tag(tag)

    def remove_tags(self, tags: List[str]) -> None:
        for tag in tags:
            self.remove_tag(tag)

    def clear(self) -> None:
        self.tags.clear()
        self.namespaced_tags.clear()

    # ── query ─────────────────────────────────────────────────────────────

    @property
    def all_tags(self) -> List[str]:
        """Return all tags including namespaced ones."""
        result = list(self.tags)
        result.extend(f"{ns}:{val}" for ns, val in self.namespaced_tags.items())
        return result

    @property
    def tag_count(self) -> int:
        return len(self.tags) + len(self.namespaced_tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tags": self.tags,
            "namespaced_tags": self.namespaced_tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentTags":
        return cls(
            tags=data.get("tags", []),
            namespaced_tags=data.get("namespaced_tags", {}),
        )

    def __repr__(self) -> str:
        return f"ExperimentTags(count={self.tag_count})"
