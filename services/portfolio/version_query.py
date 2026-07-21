"""
Version query.
"""


class VersionQuery:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def history(self):
        return self.repository.list_all()