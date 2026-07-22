"""
Pre-trade engine.
"""


class PreTradeRiskEngine:

    def __init__(
        self,
        validator,
        decision_engine,
    ):

        self.validator = validator

        self.decision_engine = decision_engine

    def check(
        self,
        request,
    ):

        valid = self.validator.validate(
            request,
        )

        return self.decision_engine.decide(
            valid,
        )