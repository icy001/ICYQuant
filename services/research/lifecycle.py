"""
Artifact lifecycle.
"""


class ArtifactLifecycle:
    def __init__(
        self,
        repository=None,
        storage=None,
        version_manager=None,
    ):
        self.repository = repository
        self.storage = storage
        self.version_manager = version_manager

    def archive(
        self,
        artifact,
    ):
        return artifact

    def publish(
        self,
        artifact,
        content,
    ):
        return artifact