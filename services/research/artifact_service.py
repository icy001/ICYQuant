"""
Artifact service.
"""

from .artifact_registry import ArtifactRegistry


class ArtifactService:
    def __init__(
        self,
        registry: ArtifactRegistry,
    ):
        self.registry = registry

    def register(
        self,
        artifact,
    ):
        self.registry.register(artifact)
        return artifact