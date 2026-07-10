from services.security import (
    RBACService,
    Role,
    Permission,
)


def test_trader_permission():
    service = RBACService()

    assert (
        service.has_permission(
            Role.TRADER,
            Permission.CREATE_ORDER
        )
        is True
    )


def test_auditor_cannot_trade():
    service = RBACService()

    assert (
        service.has_permission(
            Role.AUDITOR,
            Permission.CREATE_ORDER
        )
        is False
    )