"""
Rebalance service.
"""


class RebalanceService:
    def __init__(
        self,
        engine,
        generator,
    ):
        self.engine = engine
        self.generator = generator

    def rebalance(
        self,
        current,
        target,
    ):
        requests = self.engine.evaluate(current, target)
        return self.generator.generate(requests)