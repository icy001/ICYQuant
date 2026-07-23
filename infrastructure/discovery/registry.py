"""
Service registry.
"""


class ServiceRegistry:

    def __init__(self):
        self.services = {}

    def register(
        self,
        instance,
    ):
        self.services.setdefault(
            instance.name,
            []
        ).append(instance)

    def get(
        self,
        name,
    ):
        return self.services.get(
            name,
            []
        )