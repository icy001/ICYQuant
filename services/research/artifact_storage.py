"""
Artifact storage.
"""


class ArtifactStorage:

    def __init__(self):

        self._storage = {}

    def upload(
        self,
        artifact_id,
        content,
    ):

        self._storage[
            artifact_id
        ] = content

    def download(
        self,
        artifact_id,
    ):

        return self._storage.get(
            artifact_id
        )

    def save(
        self,
        artifact,
    ):

        return artifact.location