from datetime import datetime

from services.research import (
    WorkspaceMember,
    PermissionManager,
)


def test_permission():

    member = WorkspaceMember(
        "USER001",
        "TEAM001",
        "OWNER",
    )

    manager = PermissionManager()

    assert manager.has_permission(
        member,
        "review",
    )


def test_comment():

    from services.research import (
        Comment,
        CommentService,
    )

    service = CommentService()

    service.add(
        Comment(
            "C001",
            "USER001",
            "Looks good.",
            datetime.utcnow(),
        )
    )

    assert len(
        service.list_all()
    ) == 1