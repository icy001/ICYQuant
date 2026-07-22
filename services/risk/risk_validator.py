"""
Risk validator.
"""


class RiskValidator:

    def validate(
        self,
        request,
    ):

        return request.quantity > 0