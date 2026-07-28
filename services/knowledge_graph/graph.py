class KnowledgeGraph:

    def __init__(self):

        self.entities = {}

        self.relations = []

    def add_entity(self, entity):

        self.entities[
            entity.entity_id
        ] = entity

    def add_relation(self, relation):

        self.relations.append(
            relation
        )
