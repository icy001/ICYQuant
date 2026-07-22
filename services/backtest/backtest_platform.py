"""
Unified backtesting platform.
"""


class BacktestPlatform:

    def __init__(
        self,
        bootstrap,
        workflow,
    ):

        self.bootstrap = bootstrap

        self.workflow = workflow

    def start(
        self,
        dependencies,
        modules,
        workflow,
        context,
    ):

        self.bootstrap.initialize(
            dependencies,
            modules,
        )

        return self.workflow.execute(
            workflow,
            context,
        )