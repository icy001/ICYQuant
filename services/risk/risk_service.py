"""
Risk service implementations.
"""


class RiskService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def evaluate(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.evaluate(
            *args,
            **kwargs,
        )


class EnterpriseRiskService:

    def __init__(
        self,
        orchestrator,
        decision_engine,
    ):

        self.orchestrator = orchestrator

        self.decision_engine = decision_engine

    def evaluate(
        self,
        context,
        risk_score,
    ):

        self.orchestrator.evaluate(
            context,
        )

        return self.decision_engine.decide(
            risk_score,
        )