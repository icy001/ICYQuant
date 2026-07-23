"""
Log storage abstraction.
"""


class LogStorage:

    def __init__(self):
        self.storage = []

    def save(
        self,
        event,
    ):
        self.storage.append(event)

    def query(self):
        return self.storage