"""
AI Investment OS service.
"""


class InvestmentOSService:

    def __init__(
        self,
        workflow,
        memory,
    ):

        self.workflow = workflow

        self.memory = memory

    def execute(
        self,
        objective,
    ):

        result = self.workflow.run(
            objective
        )

        self.memory.add_memory(
            objective,
            result,
        )

        return result