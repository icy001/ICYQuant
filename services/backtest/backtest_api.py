"""
Unified backtesting API.
"""


class BacktestAPI:

    def __init__(
        self,
        platform,
    ):

        self.platform = platform

    def run(
        self,
        workflow,
        context,
        dependencies,
        modules,
    ):

        return self.platform.start(
            dependencies,
            modules,
            workflow,
            context,
        )