"""
Audit storage abstraction.
"""


class AuditStorage:


    def __init__(self):

        self.records = []


    def append(

        self,

        record,

    ):

        self.records.append(record)


    def all(self):

        return self.records