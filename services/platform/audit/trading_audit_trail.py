"""
Trading audit trail.
"""


class TradingAuditTrail:

    def __init__(self):
        self.events = []

    def append(
        self,
        event,
    ):
        self.events.append(event)

    def list(self):
        return self.events