"""
Knowledge tag.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeTag:
    name: str