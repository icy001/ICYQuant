"""
AI session context.
"""


class AISession:

    def __init__(self):

        self.messages = []

    def append(
        self,
        message,
    ):

        self.messages.append(
            message
        )

    def history(self):

        return self.messages