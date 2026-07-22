"""
Backtest cluster.
"""


class BacktestCluster:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine


    def execute(self):

        self.engine.run()