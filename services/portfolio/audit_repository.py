"""
Audit repository.
"""


class AuditRepository:

    def __init__(self):

        self.records = []

    def save(
        self,
        record,
    ):

        self.records.append(
            record
        )

    def list_all(self):

        return self.records