"""
Access policy.
"""


class AccessPolicy:
    def allow(
        self,
        role,
        permission,
    ):
        return role.name == "ADMIN"