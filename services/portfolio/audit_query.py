"""
Audit query interface.
"""


class AuditQuery:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def history(self):

        return self.repository.list_all()