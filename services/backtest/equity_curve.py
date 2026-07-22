"""
Equity curve.
"""


class EquityCurve:

    def __init__(self):

        self.points = []


    def append(
        self,
        snapshot,
    ):

        self.points.append(
            snapshot
        )


    def history(self):

        return self.points