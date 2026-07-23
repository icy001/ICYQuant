"""
Service discovery client.
"""


class DiscoveryClient:

    def __init__(
        self,
        registry,
    ):
        self.registry = registry

    def discover(
        self,
        service_name,
    ):
        instances = self.registry.get(
            service_name
        )

        return [
            i for i in instances
            if i.status == "healthy"
        ]