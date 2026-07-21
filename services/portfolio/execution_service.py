"""
Execution service.
"""


class ExecutionService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def execute(
        self,
        tasks,
    ):

        return self.engine.execute(
            tasks,
        )