"""
Model evolution manager.
"""


class ModelEvolutionManager:

    def __init__(self):
        self.version = 1

    def evolve(self):
        self.version += 1
        return self.version