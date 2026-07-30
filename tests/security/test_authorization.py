"""
Tests for ICYQuant Authorization Service.
"""

import pytest

from services.security.authorization import (
    AuthorizationService,
    Role,
    Permission,
    ResourceType,
    ABACPolicy,
    AuthorizationError,
)


class TestAuthorizationService:
    """Test RBAC and ABAC authorization."""

    def test_default_roles(self):
        svc = AuthorizationService()
        roles = svc.list_roles()
        assert len(roles) >= 6
        role_names = {r.id for r in roles}
        assert "admin" in role_names
        assert "trader" in role_names
        assert "risk_manager" in role_names

    def test_assign_role(self):
        svc = AuthorizationService()
        svc.assign_role("user1", "trader")
        permissions = svc.get_user_permissions("user1")
        assert len(permissions) > 0

    def test_check_permission_trader(self):
        svc = AuthorizationService()
        svc.assign_role("trader1", "trader")
        assert svc.check_permission("trader1", ResourceType.TRADE, Permission.READ) is True
        assert svc.check_permission("trader1", ResourceType.TRADE, Permission.WRITE) is True
        assert svc.check_permission("trader1", ResourceType.AUDIT_LOG, Permission.READ) is False

    def test_check_permission_admin(self):
        svc = AuthorizationService()
        svc.assign_role("admin1", "admin")
        assert svc.check_permission("admin1", ResourceType.SYSTEM, Permission.ADMIN) is True
        assert svc.check_permission("admin1", ResourceType.POLICY, Permission.WRITE) is True

    def test_check_permission_no_role(self):
        svc = AuthorizationService()
        assert svc.check_permission("user_no_role", ResourceType.TRADE, Permission.READ) is False

    def test_create_custom_role(self):
        svc = AuthorizationService()
        custom_role = Role(
            id="custom",
            name="Custom Role",
            description="Custom test role",
        )
        svc.create_role(custom_role)
        retrieved = svc.get_role("custom")
        assert retrieved is not None
        assert retrieved.name == "Custom Role"

    def test_revoke_role(self):
        svc = AuthorizationService()
        svc.assign_role("user1", "trader")
        svc.revoke_role("user1", "trader")
        permissions = svc.get_user_permissions("user1")
        assert len(permissions) == 0

    def test_abac_policy(self):
        svc = AuthorizationService()
        policy = ABACPolicy(
            id="policy1",
            name="Allow during market hours",
            description="Allow trading when market is open",
            attribute="market_status",
            operator="eq",
            value="open",
            effect="allow",
        )
        svc.create_abac_policy(policy)
        svc.assign_role("trader1", "trader")
        has_perm = svc.check_permission(
            "trader1",
            ResourceType.TRADE,
            Permission.READ,
            context={"market_status": "open"},
        )
        assert has_perm is True

    def test_system_user_bypass(self):
        svc = AuthorizationService()
        assert svc.check_permission("system", ResourceType.SYSTEM, Permission.ADMIN) is True

    def test_delete_non_system_role(self):
        svc = AuthorizationService()
        custom_role = Role(id="temp", name="Temp")
        svc.create_role(custom_role)
        svc.delete_role("temp")
        assert svc.get_role("temp") is None

    def test_cannot_delete_system_role(self):
        svc = AuthorizationService()
        with pytest.raises(AuthorizationError):
            svc.delete_role("admin")

    def test_get_status(self):
        svc = AuthorizationService()
        status = svc.to_dict()
        assert "roles" in status
        assert len(status["roles"]) > 0
