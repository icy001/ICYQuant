"""
Event Replay.
"""


class EventReplay:

    def replay(
        self,
        events,
        router,
    ):

        for event in events:

            router.dispatch(event)