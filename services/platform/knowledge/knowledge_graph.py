"""
Knowledge graph engine.
"""


class KnowledgeGraph:

    def __init__(self):

        self.entities = {}

        self.relationships = []

    def add_entity(self, entity):

        self.entities[entity.entity_id] = entity

    def add_relationship(self, relation):

        self.relationships.append(relation)

    def entity(self, entity_id):

        return self.entities.get(entity_id)