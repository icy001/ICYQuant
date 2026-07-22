"""
Simulation runtime.
"""


class SimulationRuntime:

    def __init__(
        self,
        scheduler,
        dispatcher,
    ):

        self.scheduler = scheduler

        self.dispatcher = dispatcher


    def run(self):

        while True:

            event = self.scheduler.next_event()

            if event is None:

                break

            self.dispatcher.dispatch(
                event,
            )