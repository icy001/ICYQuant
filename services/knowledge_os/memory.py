class KnowledgeMemory:
    def __init__(self):
        self.records = []

    def save(self, item):
        self.records.append(item)
