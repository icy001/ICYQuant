"""
Concentration validator.
"""


class ConcentrationValidator:

    def validate(
        self,
        weight,
        limit,
    ):

        return weight <= limit.max_weight