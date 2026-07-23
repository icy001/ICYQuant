"""
Investment thesis manager.
"""


class InvestmentThesisManager:

    def __init__(self):

        self.theses = []

    def create(
        self,
        thesis,
    ):

        self.theses.append(thesis)

    def list(self):

        return self.theses