"""
Trade journal.
"""


class TradeJournal:

    def __init__(
        self,
        recorder,
    ):

        self.recorder = recorder


    def entries(self):

        return self.recorder.list_all()