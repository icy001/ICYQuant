from services.data.access import (
    Role,
    DatasetACL,
    Permission,
    AccessPolicy,
    AccessAudit,
    AccessService,
)


def test_dataset_permission():
    role = Role("QUANT")

    acl = DatasetACL()

    acl.grant(role, "NVDA_DATA")

    assert acl.allowed(role, "NVDA_DATA")


def test_dataset_permission_not_allowed():
    role = Role("QUANT")
    other_role = Role("TRADER")

    acl = DatasetACL()

    acl.grant(role, "NVDA_DATA")

    assert not acl.allowed(other_role, "NVDA_DATA")


def test_role():
    role = Role("ADMIN")

    assert role.name == "ADMIN"


def test_permission():
    permission = Permission(resource="Dataset:NVDA", action="READ")

    assert permission.resource == "Dataset:NVDA"
    assert permission.action == "READ"


def test_access_policy_admin():
    policy = AccessPolicy()
    admin_role = Role("ADMIN")
    permission = Permission(resource="Dataset:NVDA", action="READ")

    result = policy.allow(admin_role, permission)

    assert result is True


def test_access_policy_non_admin():
    policy = AccessPolicy()
    user_role = Role("QUANT")
    permission = Permission(resource="Dataset:NVDA", action="READ")

    result = policy.allow(user_role, permission)

    assert result is False


def test_access_audit():
    audit = AccessAudit(
        user="john",
        resource="Dataset:NVDA",
        action="READ",
        result="ALLOW",
    )

    assert audit.user == "john"
    assert audit.result == "ALLOW"


def test_access_service():
    acl = DatasetACL()
    service = AccessService(acl)

    role = Role("RESEARCHER")
    acl.grant(role, "NASDAQ_DATA")

    result = service.check(role, "NASDAQ_DATA")

    assert result is True