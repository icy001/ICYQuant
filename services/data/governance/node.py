"""
Lineage node.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LineageNode:
    name: str
    node_type: str