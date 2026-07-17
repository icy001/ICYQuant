"""
Research experiment service.
"""

from .registry import ExperimentRegistry


class ExperimentService:
    def __init__(
        self,
        registry: ExperimentRegistry,
    ):
        self.registry = registry

    def create(
        self,
        experiment,
    ):
        self.registry.register(experiment)
        return experiment