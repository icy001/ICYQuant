"""
Event replay engine.
"""


class EventReplay:

    def replay(
        self,
        events,
    ):

        state = {}

        for event in events:

            state.update(
                event.payload
            )

        return state