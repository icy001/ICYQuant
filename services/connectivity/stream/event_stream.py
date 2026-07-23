"""
Realtime event stream.
"""


class EventStream:

    def __init__(self):
        self.events = []

    def push(
        self,
        event,
    ):
        self.events.append(event)

    def consume(self):
        return self.events.pop(0)