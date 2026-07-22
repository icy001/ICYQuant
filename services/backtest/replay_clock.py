"""
Replay clock.
"""


class ReplayClock:

    def __init__(
        self,
    ):

        self.timestamp = None

    def update(
        self,
        timestamp,
    ):

        self.timestamp = timestamp

    def now(self):

        return self.timestamp