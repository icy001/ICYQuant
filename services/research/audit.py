"""
Research event audit.
"""


class ResearchEventAudit:
    def record(
        self,
        event,
    ):
        return {
            "event_type": event.event_type,
        }