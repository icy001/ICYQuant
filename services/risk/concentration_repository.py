"""
Concentration repository.
"""


class ConcentrationRepository:

    def __init__(self):

        self.data = []

    def save(
        self,
        concentration,
    ):

        self.data.append(
            concentration
        )

    def list_all(self):

        return self.data