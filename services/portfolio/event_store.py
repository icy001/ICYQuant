"""
Portfolio event store.
"""


class PortfolioEventStore:

    def __init__(self):

        self.events = []

    def append(
        self,
        event,
    ):

        self.events.append(
            event
        )

    def all_events(self):

        return self.events