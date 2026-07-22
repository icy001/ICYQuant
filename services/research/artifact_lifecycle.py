"""
Artifact lifecycle manager.
"""


class ArtifactLifecycle:

    def __init__(
        self,
        repository,
        storage,
        versions,
    ):

        self.repository = repository

        self.storage = storage

        self.versions = versions

    def publish(
        self,
        artifact,
        content,
    ):

        self.repository.save(
            artifact
        )

        self.storage.upload(
            artifact.artifact_id,
            content,
        )

        self.versions.publish(
            artifact.artifact_id,
            artifact.version,
        )

        return artifact