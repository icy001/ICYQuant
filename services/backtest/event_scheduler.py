"""
Backtest event scheduler.
"""


class EventScheduler:

    def __init__(self):

        self.events = []


    def schedule(
        self,
        event,
    ):

        self.events.append(
            event,
        )


    def next_event(self):

        if not self.events:

            return None

        return self.events.pop(0)