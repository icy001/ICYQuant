"""
Production service registry.
"""


class ServiceRegistry:

    def __init__(self):
        self.registry = {}

    def register(
        self,
        name,
        service,
    ):
        self.registry[name] = service

    def get(
        self,
        name,
    ):
        return self.registry.get(name)