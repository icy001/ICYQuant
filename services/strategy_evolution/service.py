class StrategyEvolutionService:
    def __init__(self, generator):
        self.generator = generator

    def create(self, genome):
        return self.generator.generate(genome)
