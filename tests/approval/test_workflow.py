from services.approval import (
    ApprovalQueue,
    ApprovalService,
)


def test_create_approval_request():
    queue = ApprovalQueue()

    service = ApprovalService(
        queue
    )

    request = service.create_request(
        action=
        "POSITION_REPAIR",
        payload={
            "symbol":
            "NVDA"
        },
        reason=
        "LARGE_POSITION_CHANGE"
    )

    assert request.status.value == (
        "PENDING"
    )

    assert len(
        queue.pending()
    ) == 1