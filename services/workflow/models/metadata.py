"""Workflow metadata model.

Descriptive and lifecycle metadata associated with a workflow definition:
versioning, authorship, tagging and deprecation status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MetadataKey(str, Enum):
    """Well-known metadata keys for workflow definitions."""

    NAME = "name"
    VERSION = "version"
    DESCRIPTION = "description"
    AUTHOR = "author"
    OWNER = "owner"
    TEAM = "team"
    CATEGORY = "category"
    PRIORITY = "priority"
    SLA = "sla"
    COST_CENTER = "cost_center"
    COMPLIANCE = "compliance"
    REGION = "region"
    ENVIRONMENT = "environment"


@dataclass
class WorkflowMetadata:
    """Descriptive metadata for a workflow definition.

    Captures human-readable information (name, description, author) as well as
    lifecycle signals such as deprecation. The ``custom`` dictionary allows
    arbitrary extension data to be attached without subclassing.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deprecated: bool = False
    deprecation_message: str = ""
    custom: Dict[str, Any] = field(default_factory=dict)

    def is_deprecated(self) -> bool:
        """Return ``True`` when this workflow is flagged as deprecated."""
        return self.deprecated

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the metadata to a plain dictionary suitable for JSON encoding."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": list(self.tags),
            "labels": dict(self.labels),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deprecated": self.deprecated,
            "deprecation_message": self.deprecation_message,
            "custom": dict(self.custom),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowMetadata:
        """Reconstruct :class:`WorkflowMetadata` from a serialized dictionary."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            tags=list(data.get("tags", [])),
            labels=dict(data.get("labels", {})),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
            deprecated=bool(data.get("deprecated", False)),
            deprecation_message=data.get("deprecation_message", ""),
            custom=dict(data.get("custom", {})),
        )
