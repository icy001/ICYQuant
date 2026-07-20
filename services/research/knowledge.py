"""
Research knowledge model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchKnowledge:
    knowledge_id: str
    title: str
    category: str