"""
Stress loss validator.
"""


class StressValidator:

    def validate(
        self,
        pnl_change,
        max_loss,
    ):

        return pnl_change >= -max_loss