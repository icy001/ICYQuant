"""
Exposure repository.
"""


class ExposureRepository:

    def __init__(self):

        self.exposures = []

    def save(
        self,
        exposure,
    ):

        self.exposures.append(
            exposure
        )

    def list_all(self):

        return self.exposures