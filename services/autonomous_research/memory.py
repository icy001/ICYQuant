class ResearchLoopMemory:
    def __init__(self):
        self.history = []

    def save(self, item):
        self.history.append(item)
