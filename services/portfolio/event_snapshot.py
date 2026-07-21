"""
Event snapshot integration.
"""


class EventSnapshot:

    def build(
        self,
        state,
    ):

        return {
            "snapshot": state,
        }