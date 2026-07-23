"""
Environment configuration.
"""


class Environment:

    def __init__(
        self,
        name="development",
    ):
        self.name = name

    def is_production(self):
        return self.name == "production"