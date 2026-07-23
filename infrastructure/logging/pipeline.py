"""
Central logging pipeline.
"""


class LogPipeline:

    def __init__(self):
        self.events = []

    def publish(
        self,
        event,
    ):
        self.events.append(event)

    def all(self):
        return self.events