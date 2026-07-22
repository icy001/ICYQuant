"""
Artifact version manager.
"""


class ArtifactVersionManager:

    def __init__(self):

        self._versions = {}

    def publish(
        self,
        artifact_id,
        version,
    ):

        self._versions[
            artifact_id
        ] = version

    def latest(
        self,
        artifact_id,
    ):

        return self._versions.get(
            artifact_id
        )