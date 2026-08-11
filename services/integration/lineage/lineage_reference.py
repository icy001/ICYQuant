"""Parent-reference chain for lineage traversal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage_node import LineageNode, NodeType


@dataclass
class ParentReference:
    """Captures a parent-child relationship for upward traversal."""

    parent_node_id: str
    child_node_id: str
    relationship_type: str = "PARENT_OF"
    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_node_id": self.parent_node_id,
            "child_node_id": self.child_node_id,
            "relationship_type": self.relationship_type,
            "timestamp": self.timestamp,
        }


class LineageReferenceChain:
    """Manages a set of ParentReferences for a single lineage.

    Supports building a hierarchical reference chain and resolving
    the full ancestry path for any node.
    """

    def __init__(self, lineage_id: str = "") -> None:
        self.lineage_id: str = lineage_id
        self._references: dict[str, ParentReference] = {}
        """child_node_id → ParentReference"""

    # ── Mutators ──────────────────────────────────────────────────

    def add(self, parent_node_id: str, child_node_id: str,
            relationship_type: str = "PARENT_OF") -> ParentReference:
        ref = ParentReference(
            parent_node_id=parent_node_id,
            child_node_id=child_node_id,
            relationship_type=relationship_type,
        )
        self._references[child_node_id] = ref
        return ref

    def add_node_pair(self, parent_node: LineageNode,
                      child_node: LineageNode) -> ParentReference:
        """Derive reference from two existing lineage nodes."""
        return self.add(
            parent_node_id=parent_node.node_id,
            child_node_id=child_node.node_id,
        )

    # ── Queries ───────────────────────────────────────────────────

    def get_parent(self, node_id: str) -> str:
        """Get the parent_node_id for a child node, or '' if none."""
        ref = self._references.get(node_id)
        return ref.parent_node_id if ref else ""

    def get_ancestors(self, node_id: str) -> list[str]:
        """Return the full ancestor chain (oldest first, immediate parent last)."""
        ancestors: list[str] = []
        current = self.get_parent(node_id)
        visited: set[str] = set()
        while current:
            if current in visited:
                break  # guard against cycles
            visited.add(current)
            ancestors.append(current)
            current = self.get_parent(current)
        ancestors.reverse()
        return ancestors

    def is_descendant_of(self, child_node_id: str,
                         ancestor_node_id: str) -> bool:
        """Check whether child_node_id is in the subtree of ancestor_node_id."""
        return ancestor_node_id in self.get_ancestors(child_node_id)

    @property
    def node_count(self) -> int:
        return len(self._references)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "references": {
                k: v.to_dict() for k, v in self._references.items()
            },
        }
