"""
Historical replay engine.
"""


class ReplayEngine:

    def __init__(
        self,
        feed,
        clock,
    ):

        self.feed = feed

        self.clock = clock

    def next_tick(self):

        tick = self.feed.next()

        if tick is None:

            return None

        self.clock.update(
            tick.timestamp
        )

        return tick