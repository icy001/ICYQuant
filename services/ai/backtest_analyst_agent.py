"""
AI backtest analyst.
"""


class BacktestAnalystAgent:

    def __init__(
        self,
        backtest_service,
        ai_service,
    ):

        self.backtest_service = backtest_service

        self.ai_service = ai_service

    def analyze(
        self,
        strategy,
    ):

        result = self.backtest_service.run(
            strategy
        )

        return self.ai_service.execute(
            str(result)
        )