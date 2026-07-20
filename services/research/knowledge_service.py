"""
Knowledge service.
"""

from .repository import KnowledgeRepository


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepository,
    ):
        self.repository = repository

    def publish(
        self,
        knowledge,
    ):
        self.repository.save(knowledge)
        return knowledge