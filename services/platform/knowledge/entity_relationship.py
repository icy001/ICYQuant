"""
Knowledge graph relationship.
"""

from dataclasses import dataclass


@dataclass
class EntityRelationship:

    source: str

    relation: str

    target: str