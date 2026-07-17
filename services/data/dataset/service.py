"""
Dataset version service.
"""


class DatasetService:
    def __init__(
        self,
        registry,
    ):
        self.registry = registry

    def resolve(
        self,
        name,
    ):
        return self.registry.get(name)