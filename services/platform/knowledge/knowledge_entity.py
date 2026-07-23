"""
Knowledge graph entity.
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeEntity:

    entity_id: str

    entity_type: str

    name: str

    attributes: dict = field(default_factory=dict)