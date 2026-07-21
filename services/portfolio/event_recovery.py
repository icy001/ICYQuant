"""
Event recovery.
"""


class EventRecovery:

    def recover(
        self,
        replay,
        events,
    ):

        return replay.replay(
            events,
        )