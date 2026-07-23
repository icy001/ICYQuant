"""
Long running transaction.
"""


class LongRunningTransaction:

    def __init__(self):

        self.transactions = {}

    def begin(
        self,
        tx_id,
    ):

        self.transactions[tx_id] = "RUNNING"

    def finish(
        self,
        tx_id,
    ):

        self.transactions[tx_id] = "COMPLETED"