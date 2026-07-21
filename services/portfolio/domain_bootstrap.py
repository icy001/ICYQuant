"""
Portfolio bootstrap.
"""


class PortfolioBootstrap:

    def __init__(
        self,
        registry,
    ):

        self.registry = registry

    def initialize(self):

        return len(
            self.registry.modules
        )