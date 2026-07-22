"""
Parallel backtest engine.
"""


class ParallelBacktestEngine:

    def __init__(
        self,
        replay,
        coordinator,
    ):

        self.replay = replay

        self.coordinator = coordinator


    def run(self):

        while True:

            tick = self.replay.next_tick()

            if tick is None:

                break

            self.coordinator.execute(
                tick
            )