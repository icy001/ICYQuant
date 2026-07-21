"""
Portfolio event sourcing engine.
"""


class PortfolioEventSourcingEngine:

    def __init__(
        self,
        store,
        replay,
    ):

        self.store = store

        self.replay = replay

    def append(
        self,
        event,
    ):

        self.store.append(
            event,
        )

    def rebuild(self):

        return self.replay.replay(
            self.store.all_events()
        )