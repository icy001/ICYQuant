"""
Historical replay data feed.
"""


class ReplayFeed:

    def __init__(
        self,
        session,
        cursor,
    ):

        self.session = session

        self.cursor = cursor

    def next(self):

        if self.cursor.current() >= self.session.size():

            return None

        tick = self.session.ticks[
            self.cursor.current()
        ]

        self.cursor.advance()

        return tick