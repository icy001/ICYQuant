"""
Trade recorder.
"""


class TradeRecorder:

    def __init__(self):

        self.records = []


    def record(
        self,
        trade,
    ):

        self.records.append(
            trade
        )


    def list_all(self):

        return self.records