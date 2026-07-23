"""
Central metrics manager.
"""


class MetricsManager:

    def __init__(
        self,
        registry,
    ):
        self.registry = registry

    def snapshot(self):
        return self.registry.metrics