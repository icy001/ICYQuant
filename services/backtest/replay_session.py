"""
Replay session.
"""


class ReplaySession:

    def __init__(
        self,
        ticks,
    ):

        self.ticks = ticks

    def size(self):

        return len(
            self.ticks
        )