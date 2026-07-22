"""
Artifact service.
"""


class ArtifactService:

    def __init__(
        self,
        registry=None,
        lifecycle=None,
    ):

        self.registry = registry
        self.lifecycle = lifecycle

    def publish(
        self,
        artifact,
        content,
    ):

        return self.lifecycle.publish(
            artifact,
            content,
        )

    def register(
        self,
        artifact,
    ):

        if self.registry:
            self.registry.register(artifact)
        return artifact