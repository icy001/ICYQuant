"""
Retry strategy.
"""


class RetryPolicy:

    def __init__(
        self,
        attempts=3,
    ):
        self.attempts = attempts

    def should_retry(
        self,
        count,
    ):
        return count < self.attempts