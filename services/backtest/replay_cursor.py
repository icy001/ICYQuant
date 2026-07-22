"""
Replay cursor.
"""


class ReplayCursor:

    def __init__(
        self,
    ):

        self.index = 0

    def current(self):

        return self.index

    def advance(self):

        self.index += 1