class DataGovernanceMemory:
    def __init__(self):
        self.history = []

    def save(self, event):
        self.history.append(event)
