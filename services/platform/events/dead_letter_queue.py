"""
Dead Letter Queue.
"""


class DeadLetterQueue:

    def __init__(self):

        self.failed = []

    def push(
        self,
        event,
        reason,
    ):

        self.failed.append(
            {
                "event": event,
                "reason": reason,
            }
        )