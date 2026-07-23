"""
Event Streaming.
"""


class EventStream:

    def __init__(self):

        self.events = []

    def append(
        self,
        event,
    ):

        self.events.append(event)

    def read_all(self):

        return self.events