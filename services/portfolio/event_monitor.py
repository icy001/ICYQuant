"""
Event monitor.
"""


class EventMonitor:

    def metrics(
        self,
        events,
    ):

        return {
            "total_events": len(events),
        }