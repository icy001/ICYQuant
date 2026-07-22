"""
Review workflow.
"""


class ReviewWorkflow:

    def review(
        self,
        artifact,
        reviewer,
    ):

        return {
            "artifact":
                artifact.artifact_id,
            "reviewer":
                reviewer,
            "status":
                "APPROVED",
        }