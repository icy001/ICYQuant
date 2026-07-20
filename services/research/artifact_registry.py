"""
Artifact registry.
"""


class ArtifactRegistry:
    def __init__(self):
        self._artifacts = {}

    def register(
        self,
        artifact,
    ):
        self._artifacts[artifact.artifact_id] = artifact

    def get(
        self,
        artifact_id,
    ):
        return self._artifacts.get(artifact_id)