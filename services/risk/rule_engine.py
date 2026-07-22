"""
Risk rule engine.
"""


class RiskRuleEngine:

    def __init__(
        self,
        repository,
        pipeline,
    ):

        self.repository = repository

        self.pipeline = pipeline

    def execute(
        self,
        context,
    ):

        return self.pipeline.execute(
            self.repository.list_all(),
            context,
        )