class StrategyEvolutionMemory:
    def __init__(self):
        self.history = []

    def save(self, strategy):
        self.history.append(strategy)
