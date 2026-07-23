"""
Financial world model.
"""


class FinancialWorldModel:

    def __init__(self):

        self.state = {}

    def update(
        self,
        factor,
        value,
    ):

        self.state[factor] = value

    def snapshot(self):

        return self.state