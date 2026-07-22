"""
Position ledger.
"""


class PositionLedger:

    def __init__(self):

        self.positions = {}


    def update(
        self,
        symbol,
        quantity,
    ):

        self.positions[symbol] = (
            self.positions.get(
                symbol,
                0,
            )
            + quantity
        )


    def holdings(self):

        return dict(
            self.positions
        )