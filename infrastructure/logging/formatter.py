"""
Log formatter.
"""


class LogFormatter:

    def format(
        self,
        event,
    ):
        return {
            "formatted":
                True,
            "event":
                event
        }