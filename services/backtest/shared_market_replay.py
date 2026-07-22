"""
Shared market replay.
"""


class SharedMarketReplay:

    def __init__(
        self,
        replay_engine,
    ):

        self.replay_engine = replay_engine


    def next_tick(self):

        return self.replay_engine.next_tick()