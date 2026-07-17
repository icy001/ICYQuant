"""
Access control service.
"""


class AccessService:
    def __init__(
        self,
        acl,
    ):
        self.acl = acl

    def check(
        self,
        role,
        dataset,
    ):
        return self.acl.allowed(role, dataset)