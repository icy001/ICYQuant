"""
Projection rebuilder.
"""


class ProjectionRebuilder:

    def rebuild(
        self,
        replay,
        events,
    ):

        return replay.replay(
            events,
        )