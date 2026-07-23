"""
Workflow execution monitoring.
"""


class WorkflowMonitor:

    def __init__(self):

        self.events = []

    def record(
        self,
        event,
    ):

        self.events.append(
            event
        )

    def history(self):

        return self.events