"""
Liquidity calculator.
"""


class LiquidityCalculator:

    def calculate_volume_ratio(
        self,
        order_quantity,
        average_volume,
    ):

        if average_volume == 0:

            return float(
                "inf"
            )

        return (
            order_quantity
            /
            average_volume
        )