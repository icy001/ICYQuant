"""
Event repository.
"""


class EventRepository:

    def __init__(self):

        self.events = []

    def save(
        self,
        event,
    ):

        self.events.append(
            event
        )

    def list_all(self):

        return self.events