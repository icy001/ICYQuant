"""
Dataset ACL.
"""


class DatasetACL:
    def __init__(self):
        self.rules = {}

    def grant(
        self,
        role,
        dataset,
    ):
        self.rules.setdefault(dataset, []).append(role)

    def allowed(
        self,
        role,
        dataset,
    ):
        return role in self.rules.get(dataset, [])