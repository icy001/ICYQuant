"""
Artifact repository.
"""


class ArtifactRepository:

    def __init__(self):

        self._artifacts = {}

    def save(
        self,
        artifact,
    ):

        self._artifacts[
            artifact.artifact_id
        ] = artifact

    def get(
        self,
        artifact_id,
    ):

        return self._artifacts.get(
            artifact_id
        )

    def list_all(self):

        return list(
            self._artifacts.values()
        )