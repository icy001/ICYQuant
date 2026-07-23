"""
Central service discovery manager.
"""


class DiscoveryManager:

    def __init__(
        self,
        registry,
        client,
    ):
        self.registry = registry
        self.client = client

    def register(
        self,
        instance,
    ):
        self.registry.register(
            instance
        )

    def find(
        self,
        name,
    ):
        return self.client.discover(
            name
        )