"""
Audit logger.
"""


class AuditLogger:

    def __init__(self):

        self.logs = []

    def write(
        self,
        event,
    ):

        self.logs.append(event)