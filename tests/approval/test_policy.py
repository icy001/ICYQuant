from services.approval import (
    ApprovalPolicy,
)


def test_small_change_no_approval():
    policy = ApprovalPolicy()

    assert (
        policy.require_approval(
            100
        )
        is False
    )


def test_large_change_requires_approval():
    policy = ApprovalPolicy()

    assert (
        policy.require_approval(
            5000
        )
        is True
    )