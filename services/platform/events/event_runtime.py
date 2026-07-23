"""
Unified Event Runtime.
"""


class EventRuntime:

    def __init__(
        self,
        router,
        store,
        replay,
    ):

        self.router = router

        self.store = store

        self.replay = replay

    def emit(
        self,
        event,
    ):

        self.store.save(event)

        self.router.dispatch(event)

    def recover(self):

        self.replay.replay(
            self.store.load(),
            self.router,
        )