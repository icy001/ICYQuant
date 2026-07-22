"""
Commission model.
"""


class CommissionModel:

    def calculate(
        self,
        amount,
        rate,
    ):
        return amount * rate