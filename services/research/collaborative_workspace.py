"""
Collaborative research workspace.
"""


class CollaborativeWorkspace:

    def __init__(
        self,
        permission_manager,
        comment_service,
        review_workflow,
    ):

        self.permission_manager = permission_manager
        self.comment_service = comment_service
        self.review_workflow = review_workflow

    def review(
        self,
        artifact,
        member,
    ):

        if not self.permission_manager.has_permission(
            member,
            "review",
        ):

            raise PermissionError(
                "Permission denied."
            )

        return self.review_workflow.review(
            artifact,
            member.user_id,
        )