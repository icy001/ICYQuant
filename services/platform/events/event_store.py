"""
Persistent Event Store.
"""


class EventStore:

    def __init__(self):

        self.storage = []

    def save(
        self,
        event,
    ):

        self.storage.append(event)

    def load(self):

        return self.storage