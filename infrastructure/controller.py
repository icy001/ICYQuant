"""
Institutional infrastructure controller.
"""


class InfrastructureController:

    def __init__(
        self,
        runtime,
    ):
        self.runtime = runtime

    def health(self):
        return self.runtime.status()