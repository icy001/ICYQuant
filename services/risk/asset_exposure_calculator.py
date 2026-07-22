"""
Asset exposure calculator.
"""


class AssetExposureCalculator:

    def calculate(
        self,
        position,
        price,
    ):

        return position * price