"""
Knowledge repository.
"""


class KnowledgeRepository:
    def __init__(self):
        self._knowledge = {}

    def save(
        self,
        knowledge,
    ):
        self._knowledge[knowledge.knowledge_id] = knowledge

    def get(
        self,
        knowledge_id,
    ):
        return self._knowledge.get(knowledge_id)