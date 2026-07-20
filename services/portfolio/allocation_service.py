"""
Allocation service.
"""


class AllocationService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def calculate(
        self,
        targets,
        current,
    ):
        return self.engine.allocate(targets, current)