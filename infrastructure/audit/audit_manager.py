"""
Central audit manager.
"""


class AuditManager:


    def __init__(

        self,

        storage,

    ):

        self.storage = storage




    def record(

        self,

        audit_record,

    ):

        self.storage.append(

            audit_record

        )