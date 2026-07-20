"""
Compliance service.
"""


class ComplianceService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def monitor(
        self,
        rules,
        values,
    ):
        return self.engine.evaluate(rules, values)