"""
Trading command center.
"""


class TradingCommandCenter:

    def __init__(
        self,
        commander,
        analyzer,
    ):

        self.commander = commander

        self.analyzer = analyzer

    def trade(
        self,
        signal,
        risk,
    ):

        execution = self.commander.execute(
            signal,
            risk
        )

        return self.analyzer.evaluate(
            execution
        )