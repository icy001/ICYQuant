from dataclasses import dataclass


@dataclass
class KnowledgeRelation:

    source: str

    target: str

    relation_type: str
