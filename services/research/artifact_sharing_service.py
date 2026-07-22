"""
Artifact sharing service.
"""


class ArtifactSharingService:

    def share(
        self,
        artifact,
        target,
    ):

        return {
            "artifact":
                artifact.artifact_id,
            "target":
                target,
            "status":
                "SHARED",
        }