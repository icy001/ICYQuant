"""
Replay service.
"""


class ReplayService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def next_tick(self):

        return self.engine.next_tick()