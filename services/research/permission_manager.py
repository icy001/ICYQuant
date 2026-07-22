"""
Permission manager.
"""


class PermissionManager:

    def has_permission(
        self,
        member,
        permission,
    ):

        permissions = {
            "OWNER": {
                "read",
                "write",
                "review",
            },
            "RESEARCHER": {
                "read",
                "write",
            },
            "VIEWER": {
                "read",
            },
        }

        return permission in permissions.get(
            member.role,
            set(),
        )