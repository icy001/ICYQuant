class KnowledgeRepository:

    def __init__(self):

        self.graph = {}

    def save(self, key, value):

        self.graph[key] = value

    def get(self, key):

        return self.graph.get(key)
