"""
Role based access control.
"""

from __future__ import annotations

from .models import (
    Role,
)

from .permissions import (
    Permission,
)


ROLE_PERMISSIONS = {
    Role.TRADER:
    {
        Permission.VIEW_POSITION,
        Permission.CREATE_ORDER,
    },
    Role.RISK_MANAGER:
    {
        Permission.VIEW_POSITION,
        Permission.APPROVE_REPAIR,
        Permission.VIEW_AUDIT,
    },
    Role.ADMIN:
    set(
        Permission
    ),
    Role.AUDITOR:
    {
        Permission.VIEW_AUDIT,
    },
}


class RBACService:
    def has_permission(
        self,
        role: Role,
        permission: Permission,
    ):
        return permission in (
            ROLE_PERMISSIONS[role]
        )