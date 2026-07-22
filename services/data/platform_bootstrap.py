"""
Data platform bootstrap.
"""


class DataPlatformBootstrap:

    def __init__(
        self,
        container,
        registry,
    ):

        self.container = container

        self.registry = registry

    def initialize(self):

        for name, service in self.container._instances.items():

            self.registry.register(
                name,
                service,
            )

        return self.registry