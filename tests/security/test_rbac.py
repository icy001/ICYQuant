"""
Tests for ICYQuant RBAC authorization.
"""

from services.security.authorization import (
    AuthorizationService,
    Permission,
    ResourceType,
)


def test_trader_permission():
    service = AuthorizationService()
    service.assign_role("trader1", "trader")

    assert service.check_permission("trader1", ResourceType.ORDER, Permission.WRITE) is True
    assert service.check_permission("trader1", ResourceType.TRADE, Permission.EXECUTE) is True


def test_auditor_cannot_trade():
    service = AuthorizationService()
    service.assign_role("auditor1", "auditor")

    assert service.check_permission("auditor1", ResourceType.TRADE, Permission.WRITE) is False
    assert service.check_permission("auditor1", ResourceType.AUDIT_LOG, Permission.READ) is True
