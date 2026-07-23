"""
Timeout management.
"""


class TimeoutPolicy:

    def __init__(
        self,
        seconds=5,
    ):
        self.seconds = seconds

    def exceeded(
        self,
        elapsed,
    ):
        return elapsed > self.seconds