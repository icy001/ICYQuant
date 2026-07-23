"""
Central configuration loader.
"""


class ConfigurationLoader:

    def __init__(
        self,
        loader,
    ):
        self.loader = loader

    def load(
        self,
        path,
    ):
        return self.loader.load(
            path
        )