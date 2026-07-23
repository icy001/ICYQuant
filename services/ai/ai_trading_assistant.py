"""
AI Trading Assistant API service.
"""


class AITradingAssistant:

    def __init__(
        self,
        trading_agent,
        decision_engine,
    ):

        self.trading_agent = trading_agent

        self.decision_engine = decision_engine

    def evaluate(
        self,
        symbol,
    ):

        analysis = self.trading_agent.analyze(
            symbol
        )

        return self.decision_engine.decide(
            symbol,
            analysis,
        )