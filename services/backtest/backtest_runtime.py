"""
Backtest runtime.
"""


class BacktestRuntime:

    def __init__(
        self,
        runtime,
    ):

        self.runtime = runtime


    def execute(self):

        self.runtime.run()